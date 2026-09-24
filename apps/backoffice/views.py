"""Back-office pages.

Views are thin: they call `apps.backoffice.services` (or another app's services) and render a
`backoffice/*` template. No business logic lives here. `styleguide` moved here from
`apps.common.views` when M8.1 gave the back-office its own app; it stays staff-only markup with
no data behind it, so its gate is `is_staff`/DEBUG rather than the full MFA mixin.
"""

import uuid

from django.conf import settings
from django.contrib import messages
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.generic import TemplateView, View

from apps.common.email import ORDER_EMAIL_KINDS
from apps.custom_orders import services as custom_services
from apps.custom_orders.models import DesignUpload
from apps.orders import services as order_services
from apps.orders.models import Order
from apps.payments import gateway as payment_gateway
from apps.payments import services as payment_services
from apps.payments.models import Payment

from . import services
from .exports import stream_csv
from .mixins import StaffRequiredMixin


class DashboardView(StaffRequiredMixin, TemplateView):
    """The back-office landing: the O1 tiles and the two hand-rolled SVG charts."""

    template_name = "backoffice/dashboard.html"

    def get_context_data(self, **kwargs):
        return {**super().get_context_data(**kwargs), **services.dashboard_context()}


class OrderQueueView(StaffRequiredMixin, TemplateView):
    """The order queue (M8.4): saved-view presets, filters, bulk selection and a streamed CSV
    export. Viewing needs ``view_order``; the bulk action lives on its own guarded endpoint."""

    template_name = "backoffice/orders.html"
    permission_required = "orders.view_order"

    def get(self, request, *args, **kwargs):
        if request.GET.get("export") == "csv":
            filters = services.parse_order_filters(request.GET)
            return stream_csv(
                "orders.csv", services.ORDER_CSV_HEADER, services.order_queue_rows(filters)
            )
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        filters = services.parse_order_filters(self.request.GET)
        params = self.request.GET.copy()
        params.pop("page", None)
        return {
            **super().get_context_data(**kwargs),
            "orders": services.order_queue(filters, self.request.GET.get("page")),
            "filters": filters,
            "saved_views": services.order_saved_views(filters.get("view")),
            "status_choices": Order.Status.choices,
            "fulfilment_choices": Order.Fulfilment.choices,
            "payment_choices": Payment.Status.choices,
            "bulk_statuses": services.BULK_STATUS_CHOICES,
            "query": params.urlencode(),
        }


class OrderBulkActionView(StaffRequiredMixin, View):
    """POST a list of order ids and a target status. Gated by ``transition_order`` so a
    view-only role (Support) cannot reach it at all."""

    permission_required = "orders.transition_order"

    def post(self, request):
        ids = request.POST.getlist("ids")
        to_status = request.POST.get("to_status", "")
        if not ids:
            messages.warning(request, "Select at least one order.")
        elif to_status not in {value for value, _ in services.BULK_STATUS_CHOICES}:
            messages.error(request, "Choose a status to apply.")
        else:
            result = order_services.bulk_transition(
                ids, to_status, actor=request.user, note="Bulk status update"
            )
            messages.success(
                request, f"{result['moved']} order(s) moved, {result['skipped']} skipped."
            )
        query = request.POST.get("next", "").lstrip("?")
        url = reverse("backoffice:orders")
        return redirect(f"{url}?{query}" if query else url)


class OrderDetailView(StaffRequiredMixin, TemplateView):
    """One order (M8.5): the status and shipment timelines, totals, and the guarded action
    forms. Viewing needs ``view_order``; each action form is gated per its own permission and
    posts to ``OrderActionView``, which re-checks that permission server-side."""

    template_name = "backoffice/order_detail.html"
    permission_required = "orders.view_order"

    def get_context_data(self, **kwargs):
        order = get_object_or_404(
            Order.objects.select_related("user").prefetch_related(
                "items", "shipments__items", "status_events__actor", "payments"
            ),
            order_number=kwargs["order_number"],
        )
        return {
            **super().get_context_data(**kwargs),
            "order": order,
            "status_choices": Order.Status.choices,
            "email_kinds": ORDER_EMAIL_KINDS,
        }


class OrderPackingSlipView(StaffRequiredMixin, TemplateView):
    """A print-only packing slip: the address and the lines to pack, no prices needed and no
    invoice (GST dropped, Part 5)."""

    template_name = "backoffice/packing_slip.html"
    permission_required = "orders.view_order"

    def get_context_data(self, **kwargs):
        order = get_object_or_404(
            Order.objects.prefetch_related("items"), order_number=kwargs["order_number"]
        )
        return {**super().get_context_data(**kwargs), "order": order}


class OrderActionView(StaffRequiredMixin, View):
    """Every mutating action on an order (M8.5), each guarded by its own permission so a
    view-only role reaches none of them. The staff gate alone lets the request in; the real
    gate is the per-action permission checked below. Views stay thin: each handler calls a
    service and redirects back to the detail page with a message."""

    _ACTION_PERMS = {
        "advance": "orders.transition_order",
        "cancel": "orders.transition_order",
        "refund": "orders.refund_order",
        "shipment": "orders.change_order",
        "email": "orders.change_order",
        "note": "orders.change_order",
    }

    def post(self, request, order_number):
        action = request.POST.get("action", "")
        perm = self._ACTION_PERMS.get(action)
        if perm is None or not request.user.has_perm(perm):
            raise Http404
        order = get_object_or_404(Order, order_number=order_number)
        getattr(self, f"_do_{action}")(request, order)
        return redirect("backoffice:order_detail", order_number=order_number)

    def _do_advance(self, request, order):
        to_status = request.POST.get("to_status", "")
        if to_status not in Order.Status.values:
            messages.error(request, "Unknown status.")
            return
        try:
            order_services.transition(
                order, to_status, actor=request.user, note="Status change from back-office"
            )
            messages.success(request, f"Order moved to {order.get_status_display()}.")
        except order_services.OrderError as exc:
            messages.error(request, exc.message)

    def _do_cancel(self, request, order):
        try:
            order_services.cancel_order(
                order, actor=request.user, reason=request.POST.get("reason", "")
            )
            messages.success(request, "Order cancelled.")
        except order_services.OrderError as exc:
            messages.error(request, exc.message)

    def _do_refund(self, request, order):
        try:
            payment_services.refund_order(order, actor=request.user)
            messages.success(request, "Refund issued and the customer notified.")
        except (payment_gateway.PaymentError, order_services.OrderError) as exc:
            messages.error(request, exc.message)

    def _do_shipment(self, request, order):
        try:
            shipment_id = uuid.UUID(request.POST.get("shipment_id", ""))
        except (ValueError, TypeError):
            raise Http404 from None
        shipment = get_object_or_404(order.shipments, pk=shipment_id)
        order_services.update_shipment(
            shipment,
            carrier=request.POST.get("carrier", ""),
            awb=request.POST.get("awb", ""),
            tracking_url=request.POST.get("tracking_url", ""),
            mark_shipped=bool(request.POST.get("mark_shipped")),
            mark_delivered=bool(request.POST.get("mark_delivered")),
            actor=request.user,
        )
        messages.success(request, "Shipment updated.")

    def _do_email(self, request, order):
        kind = request.POST.get("kind", "")
        if kind not in ORDER_EMAIL_KINDS:
            messages.error(request, "Unknown email.")
            return
        from apps.common.email import send_order_email

        send_order_email(str(order.pk), kind)
        messages.success(request, f"Resent the {kind} email.")

    def _do_note(self, request, order):
        note = (request.POST.get("note", "") or "").strip()
        if not note:
            messages.warning(request, "Write a note first.")
            return
        order_services.add_note(order, actor=request.user, note=note)
        messages.success(request, "Note added.")


class DesignReviewQueueView(StaffRequiredMixin, TemplateView):
    """The design moderation queue (M8.6): the M7 review flow surfaced here. Defaults to the
    flagged designs a moderator must act on; the dashboard's failed-Qikink tile links in with
    ``?submit=failed``."""

    template_name = "backoffice/designs.html"
    permission_required = "custom_orders.view_designupload"

    def get_context_data(self, **kwargs):
        return {
            **super().get_context_data(**kwargs),
            "designs": services.design_queue(self.request.GET, self.request.GET.get("page")),
            "review": self.request.GET.get("review", ""),
            "submit": self.request.GET.get("submit", ""),
            "review_choices": DesignUpload.ReviewStatus.choices,
        }


class DesignReviewDetailView(StaffRequiredMixin, TemplateView):
    """One design: full-resolution art through a short-lived signed R2 GET, its dimensions, the
    bound custom lines with their Qikink status and AWB, and the approve/reject/resubmit forms."""

    template_name = "backoffice/design_detail.html"
    permission_required = "custom_orders.view_designupload"

    def get_context_data(self, **kwargs):
        design = get_object_or_404(
            DesignUpload.objects.select_related("user").prefetch_related(
                "front_orders__order", "back_orders__order"
            ),
            pk=kwargs["pk"],
        )
        return {
            **super().get_context_data(**kwargs),
            "design": design,
            "print_link": custom_services.design_link(design),
            "bound_orders": [*design.front_orders.all(), *design.back_orders.all()],
        }


class DesignReviewActionView(StaffRequiredMixin, View):
    """Approve, reject or resubmit from the design detail page. Approve/reject need
    ``change_designupload``; resubmit needs ``change_customdesignorder``."""

    _ACTION_PERMS = {
        "approve": "custom_orders.change_designupload",
        "reject": "custom_orders.change_designupload",
        "resubmit": "custom_orders.change_customdesignorder",
    }

    def post(self, request, pk):
        action = request.POST.get("action", "")
        perm = self._ACTION_PERMS.get(action)
        if perm is None or not request.user.has_perm(perm):
            raise Http404
        design = get_object_or_404(DesignUpload, pk=pk)
        if action == "resubmit":
            self._resubmit(request, design)
        else:
            custom_services.review_design(
                design, approve=action == "approve", reason=request.POST.get("reason", "")
            )
            messages.success(request, f"Design {action}d.")
        return redirect("backoffice:design_detail", pk=pk)

    def _resubmit(self, request, design):
        results = [
            custom_services.resubmit_design(custom)
            for custom in (*design.front_orders.all(), *design.back_orders.all())
        ]
        submitted = results.count("submitted")
        if submitted:
            messages.success(request, f"Resubmitted {submitted} line(s) to Qikink.")
        else:
            messages.warning(request, "Nothing to resubmit (unpaid or already submitted).")


def styleguide(request):
    """Every component in every state, staff only.

    A 404 rather than a redirect, matching `StaffAdminMiddleware`: a page you may not see should
    not confirm that it exists. DEBUG opens it so a developer reaches it without staff
    credentials; it is only markup with no data behind it, and production forces DEBUG off.
    """
    if not (settings.DEBUG or (request.user.is_authenticated and request.user.is_staff)):
        raise Http404
    return render(request, "backoffice/styleguide.html")

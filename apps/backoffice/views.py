"""Back-office pages.

Views are thin: they call `apps.backoffice.services` (or another app's services) and render a
`backoffice/*` template. No business logic lives here. `styleguide` moved here from
`apps.common.views` when M8.1 gave the back-office its own app; it stays staff-only markup with
no data behind it, so its gate is `is_staff`/DEBUG rather than the full MFA mixin.
"""

import uuid
from decimal import Decimal, InvalidOperation

from django.conf import settings
from django.contrib import messages
from django.db import transaction
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.generic import TemplateView, View

from apps.catalog import services as catalog_services
from apps.catalog.forms import ImageFormSet, ProductForm, VariantFormSet
from apps.catalog.models import Product
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


def _product_decimal(raw):
    """A price from a posted string, or None when it is blank or junk so the service skips it."""
    try:
        value = Decimal((raw or "").strip())
    except (InvalidOperation, TypeError):
        return None
    return value if value >= 0 else None


class ProductListView(StaffRequiredMixin, TemplateView):
    """The product list (M8.7): search, an active/archived filter, and inline base-price and
    active editing across the page. Viewing needs ``view_product``; the bulk save is its own
    guarded endpoint so a view-only role cannot write."""

    template_name = "backoffice/products.html"
    permission_required = "catalog.view_product"

    def get_context_data(self, **kwargs):
        params = self.request.GET.copy()
        params.pop("page", None)
        return {
            **super().get_context_data(**kwargs),
            "products": services.product_admin_list(self.request.GET, self.request.GET.get("page")),
            "q": self.request.GET.get("q", ""),
            "status": self.request.GET.get("status", ""),
            "low_stock_threshold": settings.LOW_STOCK_THRESHOLD,
            "query": params.urlencode(),
        }


class ProductBulkUpdateView(StaffRequiredMixin, View):
    """Apply the list's inline base-price and active edits. Gated by ``change_product`` so a
    view-only role cannot reach it."""

    permission_required = "catalog.change_product"

    def post(self, request):
        updates = {
            raw: {
                "base_price": _product_decimal(request.POST.get(f"price-{raw}")),
                "is_active": bool(request.POST.get(f"active-{raw}")),
            }
            for raw in request.POST.getlist("ids")
        }
        changed = catalog_services.bulk_update_products(updates)
        messages.success(request, f"{changed} product(s) updated.")
        query = request.POST.get("next", "").lstrip("?")
        url = reverse("backoffice:products")
        return redirect(f"{url}?{query}" if query else url)


class _ProductFormMixin(StaffRequiredMixin):
    """Shared render and save for the create and edit product forms: one ModelForm plus the
    variant matrix and the image reorder formset, all saved in a single transaction."""

    template_name = "backoffice/product_form.html"

    def _render(self, request, product, form, variants, images):
        return render(
            request,
            self.template_name,
            {
                "product": product,
                "form": form,
                "variant_formset": variants,
                "image_formset": images,
            },
        )

    def _save(self, request, product):
        form = ProductForm(request.POST, request.FILES, instance=product)
        variants = VariantFormSet(request.POST, instance=product)
        images = ImageFormSet(request.POST, instance=product)
        if form.is_valid() and variants.is_valid() and images.is_valid():
            with transaction.atomic():
                product = form.save()
                variants.instance = product
                variants.save()
                images.instance = product
                images.save()
                catalog_services.index_product_images(product, request.FILES.getlist("gallery"))
            messages.success(request, "Product saved.")
            return redirect("backoffice:product_edit", pk=product.pk)
        messages.error(request, "Fix the errors below and save again.")
        return self._render(request, product, form, variants, images)


class ProductCreateView(_ProductFormMixin, View):
    permission_required = "catalog.add_product"

    def get(self, request):
        return self._render(request, None, ProductForm(), VariantFormSet(), ImageFormSet())

    def post(self, request):
        return self._save(request, None)


class ProductEditView(_ProductFormMixin, View):
    permission_required = "catalog.change_product"

    def get(self, request, pk):
        product = get_object_or_404(Product, pk=pk)
        return self._render(
            request,
            product,
            ProductForm(instance=product),
            VariantFormSet(instance=product),
            ImageFormSet(instance=product),
        )

    def post(self, request, pk):
        return self._save(request, get_object_or_404(Product, pk=pk))


class ProductActionView(StaffRequiredMixin, View):
    """Archive, restore or duplicate one product, each re-checking its own permission (the
    ``OrderActionView`` pattern) so a view-only role reaches none of them. There is no delete: a
    product is archived, never removed."""

    _ACTION_PERMS = {
        "archive": "catalog.change_product",
        "unarchive": "catalog.change_product",
        "duplicate": "catalog.add_product",
    }

    def post(self, request, pk):
        action = request.POST.get("action", "")
        perm = self._ACTION_PERMS.get(action)
        if perm is None or not request.user.has_perm(perm):
            raise Http404
        product = get_object_or_404(Product, pk=pk)
        if action == "duplicate":
            clone = catalog_services.duplicate_product(product)
            messages.success(request, "Duplicated as an inactive draft.")
            return redirect("backoffice:product_edit", pk=clone.pk)
        catalog_services.set_product_active(product, action == "unarchive")
        messages.success(
            request, "Product restored." if action == "unarchive" else "Product archived."
        )
        return redirect("backoffice:products")


class ProductImportView(StaffRequiredMixin, View):
    """CSV export and a two-step import (C16). Export streams; import previews the diff, carrying
    the raw CSV in a hidden field, and only writes on the confirmed second post, so nothing is
    stored on the read-only filesystem between the steps."""

    permission_required = ("catalog.add_product", "catalog.change_product")
    template_name = "backoffice/product_import.html"

    def get(self, request):
        if request.GET.get("export") == "csv":
            return stream_csv(
                "products.csv",
                catalog_services.PRODUCT_CSV_HEADER,
                catalog_services.product_export_rows(catalog_services.exportable_products()),
            )
        return render(request, self.template_name, self._context())

    def post(self, request):
        if request.POST.get("step") == "confirm":
            result = catalog_services.apply_product_import(request.POST.get("csv", ""))
            messages.success(
                request,
                f"Imported: {result['created']} created, {result['updated']} updated, "
                f"{result['errors']} skipped.",
            )
            return redirect("backoffice:products")
        upload = request.FILES.get("file")
        if upload is None:
            messages.warning(request, "Choose a CSV file to import.")
            return redirect("backoffice:product_import")
        text = upload.read().decode("utf-8-sig", errors="replace")
        return render(
            request,
            self.template_name,
            self._context(plan=catalog_services.plan_product_import(text), csv_text=text),
        )

    def _context(self, plan=None, csv_text=""):
        return {"header": catalog_services.PRODUCT_CSV_HEADER, "plan": plan, "csv_text": csv_text}


def styleguide(request):
    """Every component in every state, staff only.

    A 404 rather than a redirect, matching `StaffAdminMiddleware`: a page you may not see should
    not confirm that it exists. DEBUG opens it so a developer reaches it without staff
    credentials; it is only markup with no data behind it, and production forces DEBUG off.
    """
    if not (settings.DEBUG or (request.user.is_authenticated and request.user.is_staff)):
        raise Http404
    return render(request, "backoffice/styleguide.html")

"""Back-office pages.

Views are thin: they call `apps.backoffice.services` (or another app's services) and render a
`backoffice/*` template. No business logic lives here. `styleguide` moved here from
`apps.common.views` when M8.1 gave the back-office its own app; it stays staff-only markup with
no data behind it, so its gate is `is_staff`/DEBUG rather than the full MFA mixin.
"""

from django.conf import settings
from django.contrib import messages
from django.http import Http404
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.generic import TemplateView, View

from apps.orders import services as order_services
from apps.orders.models import Order
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


def styleguide(request):
    """Every component in every state, staff only.

    A 404 rather than a redirect, matching `StaffAdminMiddleware`: a page you may not see should
    not confirm that it exists. DEBUG opens it so a developer reaches it without staff
    credentials; it is only markup with no data behind it, and production forces DEBUG off.
    """
    if not (settings.DEBUG or (request.user.is_authenticated and request.user.is_staff)):
        raise Http404
    return render(request, "backoffice/styleguide.html")

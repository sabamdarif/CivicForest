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
from django.contrib.auth import get_user_model
from django.db import transaction
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.generic import TemplateView, View

from apps.cart.forms import CouponForm
from apps.cart.models import Coupon
from apps.catalog import services as catalog_services
from apps.catalog.forms import (
    CategoryForm,
    CollectionForm,
    ImageFormSet,
    ProductForm,
    StockAdjustmentForm,
    VariantFormSet,
)
from apps.catalog.models import Category, Collection, Product, ProductVariant
from apps.common import email as common_email
from apps.common.email import ORDER_EMAIL_KINDS
from apps.common.models import StockAdjustment
from apps.content.forms import AnnouncementBarForm, HomeSectionForm
from apps.content.models import AnnouncementBar, HomeSection
from apps.custom_orders import services as custom_services
from apps.custom_orders.models import DesignUpload
from apps.orders import services as order_services
from apps.orders.models import Order
from apps.payments import gateway as payment_gateway
from apps.payments import services as payment_services
from apps.payments.models import Payment

from . import cron, services
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


class InventoryView(StaffRequiredMixin, TemplateView):
    """Stock on hand (M8.8, O6): every variant with its count and threshold, searchable and
    filterable to low stock, with a per-row adjustment form and a streamed CSV export. Viewing
    needs ``view_productvariant``; the adjustment posts to its own guarded endpoint."""

    template_name = "backoffice/inventory.html"
    permission_required = "catalog.view_productvariant"

    def get(self, request, *args, **kwargs):
        if request.GET.get("export") == "csv":
            return stream_csv(
                "inventory.csv", services.INVENTORY_CSV_HEADER, services.inventory_rows(request.GET)
            )
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        params = self.request.GET.copy()
        params.pop("page", None)
        return {
            **super().get_context_data(**kwargs),
            "variants": services.inventory_list(self.request.GET, self.request.GET.get("page")),
            "q": self.request.GET.get("q", ""),
            "low": self.request.GET.get("low", ""),
            "reasons": StockAdjustment.Reason.choices,
            "query": params.urlencode(),
        }


class StockAdjustView(StaffRequiredMixin, View):
    """Apply one stock adjustment (O6), gated by ``add_stockadjustment`` so only a stock role can
    reach it. The change and its reason are written together; a change below zero is refused."""

    permission_required = "common.add_stockadjustment"

    def post(self, request, pk):
        variant = get_object_or_404(ProductVariant, pk=pk)
        form = StockAdjustmentForm(request.POST)
        if not form.is_valid():
            messages.error(request, "Enter a non-zero change and a reason.")
        else:
            try:
                catalog_services.adjust_stock(
                    variant,
                    form.cleaned_data["delta"],
                    reason=form.cleaned_data["reason"],
                    actor=request.user,
                    note=form.cleaned_data["note"],
                )
                messages.success(request, "Stock adjusted.")
            except catalog_services.StockError as exc:
                messages.error(request, exc.message)
        query = request.POST.get("next", "").lstrip("?")
        url = reverse("backoffice:inventory")
        return redirect(f"{url}?{query}" if query else url)


class CouponListView(StaffRequiredMixin, TemplateView):
    """Coupons with their live redemption counts (M8.9, O7). Viewing needs ``view_coupon``; create,
    edit and retire are guarded endpoints below."""

    template_name = "backoffice/coupons.html"
    permission_required = "cart.view_coupon"

    def get_context_data(self, **kwargs):
        params = self.request.GET.copy()
        params.pop("page", None)
        return {
            **super().get_context_data(**kwargs),
            "coupons": services.coupon_list(self.request.GET, self.request.GET.get("page")),
            "q": self.request.GET.get("q", ""),
            "status": self.request.GET.get("status", ""),
            "query": params.urlencode(),
        }


class _CouponFormMixin(StaffRequiredMixin):
    template_name = "backoffice/coupon_form.html"

    def _render(self, request, coupon, form):
        return render(request, self.template_name, {"coupon": coupon, "form": form})

    def _save(self, request, coupon):
        form = CouponForm(request.POST, instance=coupon)
        if form.is_valid():
            coupon = form.save()
            messages.success(request, "Coupon saved.")
            return redirect("backoffice:coupon_edit", pk=coupon.pk)
        messages.error(request, "Fix the errors below and save again.")
        return self._render(request, coupon, form)


class CouponCreateView(_CouponFormMixin, View):
    permission_required = "cart.add_coupon"

    def get(self, request):
        return self._render(request, None, CouponForm())

    def post(self, request):
        return self._save(request, None)


class CouponEditView(_CouponFormMixin, View):
    permission_required = "cart.change_coupon"

    def get(self, request, pk):
        coupon = get_object_or_404(Coupon, pk=pk)
        return self._render(request, coupon, CouponForm(instance=coupon))

    def post(self, request, pk):
        return self._save(request, get_object_or_404(Coupon, pk=pk))


class CouponActionView(StaffRequiredMixin, View):
    """Retire or restore a coupon (O7): deactivation, never a delete, so its redemption history
    survives. Gated by ``change_coupon``."""

    permission_required = "cart.change_coupon"

    def post(self, request, pk):
        action = request.POST.get("action", "")
        if action not in {"retire", "restore"}:
            raise Http404
        coupon = get_object_or_404(Coupon, pk=pk)
        coupon.is_active = action == "restore"
        coupon.save(update_fields=["is_active", "updated_at"])
        messages.success(request, "Coupon restored." if action == "restore" else "Coupon retired.")
        return redirect("backoffice:coupons")


class CouponReportView(StaffRequiredMixin, TemplateView):
    """One coupon's usage broken down per customer (O7). Read-only, needs ``view_coupon``."""

    template_name = "backoffice/coupon_report.html"
    permission_required = "cart.view_coupon"

    def get_context_data(self, **kwargs):
        coupon = get_object_or_404(Coupon, pk=kwargs["pk"])
        return {
            **super().get_context_data(**kwargs),
            "coupon": coupon,
            "usage": services.coupon_usage(coupon),
        }


class CustomerListView(StaffRequiredMixin, TemplateView):
    """Customers with paid-order count and lifetime value (M8.10, O8): search, a blocked filter and
    a streamed CSV export. Viewing needs ``view_user``; blocking is its own guarded endpoint. No
    impersonation is offered anywhere (O8)."""

    template_name = "backoffice/customers.html"
    permission_required = "accounts.view_user"

    def get(self, request, *args, **kwargs):
        if request.GET.get("export") == "csv":
            return stream_csv(
                "customers.csv", services.CUSTOMER_CSV_HEADER, services.customer_rows(request.GET)
            )
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        params = self.request.GET.copy()
        params.pop("page", None)
        return {
            **super().get_context_data(**kwargs),
            "customers": services.customer_list(self.request.GET, self.request.GET.get("page")),
            "q": self.request.GET.get("q", ""),
            "status": self.request.GET.get("status", ""),
            "query": params.urlencode(),
        }


class CustomerDetailView(StaffRequiredMixin, TemplateView):
    """One customer: their orders, lifetime value, and a block/unblock form. Needs ``view_user``."""

    template_name = "backoffice/customer_detail.html"
    permission_required = "accounts.view_user"

    def get_context_data(self, **kwargs):
        customer = get_object_or_404(get_user_model(), pk=kwargs["pk"], is_staff=False)
        return {
            **super().get_context_data(**kwargs),
            "customer": customer,
            **services.customer_detail(customer),
        }


class CustomerBlockView(StaffRequiredMixin, View):
    """Block or unblock a customer (O8): ``is_active`` toggled, never a delete, so their orders and
    history survive. Gated by ``change_user``, which only Owner holds (Manager sees but cannot alter
    user rows, O11)."""

    permission_required = "accounts.change_user"

    def post(self, request, pk):
        action = request.POST.get("action", "")
        if action not in {"block", "unblock"}:
            raise Http404
        customer = get_object_or_404(get_user_model(), pk=pk, is_staff=False)
        customer.is_active = action == "unblock"
        customer.save(update_fields=["is_active"])
        messages.success(
            request, "Customer unblocked." if action == "unblock" else "Customer blocked."
        )
        return redirect("backoffice:customer_detail", pk=pk)


class ContentView(StaffRequiredMixin, TemplateView):
    """Content hub (M8.12, O10): the announcement bars, home sections, and category and collection
    imagery, each linking to its editor. Pages and FAQ entries arrive with their M9 models."""

    template_name = "backoffice/content.html"
    permission_required = "content.view_announcementbar"

    def get_context_data(self, **kwargs):
        return {**super().get_context_data(**kwargs), **services.content_overview()}


class _ContentEditMixin(StaffRequiredMixin):
    """Shared render and save for a single content ModelForm. Subclasses set ``model``,
    ``form_class``, ``title`` and the permission; a ``pk`` in the URL edits, its absence creates."""

    form_class = None
    model = None
    title = ""
    template_name = "backoffice/content_form.html"

    def get(self, request, pk=None):
        instance = get_object_or_404(self.model, pk=pk) if pk else None
        return self._render(request, self.form_class(instance=instance))

    def post(self, request, pk=None):
        instance = get_object_or_404(self.model, pk=pk) if pk else None
        form = self.form_class(request.POST, request.FILES, instance=instance)
        if form.is_valid():
            form.save()
            messages.success(request, "Saved.")
            return redirect("backoffice:content")
        messages.error(request, "Fix the errors below and save again.")
        return self._render(request, form)

    def _render(self, request, form):
        return render(request, self.template_name, {"form": form, "title": self.title})


class AnnouncementCreateView(_ContentEditMixin, View):
    model, form_class, title = AnnouncementBar, AnnouncementBarForm, "New announcement bar"
    permission_required = "content.add_announcementbar"


class AnnouncementEditView(_ContentEditMixin, View):
    model, form_class, title = AnnouncementBar, AnnouncementBarForm, "Announcement bar"
    permission_required = "content.change_announcementbar"


class HomeSectionCreateView(_ContentEditMixin, View):
    model, form_class, title = HomeSection, HomeSectionForm, "New home section"
    permission_required = "content.add_homesection"


class HomeSectionEditView(_ContentEditMixin, View):
    model, form_class, title = HomeSection, HomeSectionForm, "Home section"
    permission_required = "content.change_homesection"


class CategoryEditView(_ContentEditMixin, View):
    model, form_class, title = Category, CategoryForm, "Category"
    permission_required = "catalog.change_category"


class CollectionEditView(_ContentEditMixin, View):
    model, form_class, title = Collection, CollectionForm, "Collection"
    permission_required = "catalog.change_collection"


class JobsPanelView(StaffRequiredMixin, TemplateView):
    """The jobs panel (M8.13): recent JobRun rows with full error text, a run-now button per
    registered job, and the OutboundEmail ledger with resend. Viewing needs ``view_jobrun``."""

    template_name = "backoffice/jobs.html"
    permission_required = "common.view_jobrun"

    def get_context_data(self, **kwargs):
        return {
            **super().get_context_data(**kwargs),
            "runs": services.recent_job_runs(self.request.GET.get("page")),
            "emails": services.recent_emails(self.request.GET.get("page")),
            "job_names": list(cron.CRON_JOBS),
        }


class JobRunNowView(StaffRequiredMixin, View):
    """Run one registered job from the panel, staff-gated (``add_jobrun``) rather than bearer-gated
    so the CRON_SECRET never reaches a browser. Uses the same runner as the cron endpoint."""

    permission_required = "common.add_jobrun"

    def post(self, request):
        run = cron.run_named_job(request.POST.get("name", ""))
        if run is None:
            raise Http404
        if run.status == run.Status.DONE:
            messages.success(request, f"{run.name}: processed {run.items_processed}.")
        else:
            messages.error(request, f"{run.name} failed: {run.last_error}")
        return redirect("backoffice:jobs")


class EmailResendView(StaffRequiredMixin, View):
    """Resend a ledgered email (M8.13), gated by ``change_outboundemail``. Re-renders from the
    stored ids, so the resend reflects live data."""

    permission_required = "common.change_outboundemail"

    def post(self, request, pk):
        result = common_email.resend(str(pk))
        if result == "sent":
            messages.success(request, "Email resent.")
        elif result == "failed":
            messages.error(request, "Resend failed; the mail server rejected it.")
        else:
            messages.warning(request, "Nothing to resend for that row.")
        return redirect("backoffice:jobs")


class ReportsView(StaffRequiredMixin, TemplateView):
    """Reports hub (M8.14, O13): sales by day, product and category, coupon performance, inventory
    valuation and zero-result searches, each exportable via the shared streamed CSV. GST summary by
    rate is omitted (Part 5). Needs ``view_order`` (these are sales and stock figures)."""

    template_name = "backoffice/reports.html"
    permission_required = "orders.view_order"

    def get(self, request, *args, **kwargs):
        report = request.GET.get("report")
        if request.GET.get("export") == "csv" and report in services.REPORTS:
            header, rows = services.report_export(report)
            return stream_csv(f"{report}.csv", header, rows)
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        return {
            **super().get_context_data(**kwargs),
            "reports": [services.report_view(name) for name in services.REPORTS],
            "window_days": services.REPORT_WINDOW_DAYS,
        }


def styleguide(request):
    """Every component in every state, staff only.

    A 404 rather than a redirect, matching `StaffAdminMiddleware`: a page you may not see should
    not confirm that it exists. DEBUG opens it so a developer reaches it without staff
    credentials; it is only markup with no data behind it, and production forces DEBUG off.
    """
    if not (settings.DEBUG or (request.user.is_authenticated and request.user.is_staff)):
        raise Http404
    return render(request, "backoffice/styleguide.html")

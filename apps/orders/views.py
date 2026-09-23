"""Order + checkout: the storefront checkout flow, the account order pages, guest tracking,
and the read-only orders JSON API.

- ``/checkout/``: the login + verified-email gated form; a valid post creates the order and
  redirects to the Razorpay pay page. Money is always computed server-side.
- ``/account/orders/``: the customer's own orders, looked up by the non-guessable public order
  number (ownership-scoped, no IDOR), with per-shipment tracking and cancellation where allowed.
- ``/track/``: a guest lookup by order number + email, rate-limited per IP.
"""

from __future__ import annotations

import re

from allauth.account.decorators import verified_email_required
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from rest_framework import mixins, status, viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.cart import services as cart_services
from apps.cart.views import cart_context
from apps.common.throttles import (
    CheckoutDayThrottle,
    CheckoutMinuteThrottle,
    TrackThrottle,
    exceeded,
)
from apps.payments import gateway as payment_gateway
from apps.payments import services as payment_services

from . import services
from .forms import CheckoutForm
from .models import Order
from .serializers import CheckoutSerializer, OrderSerializer

_CHECKOUT_KEY_RE = re.compile(r"^[A-Za-z0-9_-]{8,64}$")


# ─── Storefront: the checkout page, behind the login + verified-email gate ────
@verified_email_required
def checkout_page(request):
    """The checkout form (contact + shipping + terms), posting and re-rendering without JS.

    ``verified_email_required`` is ``login_required`` plus B2's verified-email check, so an
    unverified account is stopped here rather than sent into a payment it cannot complete.
    ``cart_context`` revalidates stock before anything is priced (G9). A valid POST snapshots
    the cart into an order, opens a Razorpay order for it, and redirects to the pay page; the
    Razorpay modal there is the one documented JS exception.
    """
    context = cart_context(request)
    addresses = list(request.user.addresses.all())
    priced = context["priced"]

    if request.method == "POST":
        form = CheckoutForm(request.POST, addresses=addresses)
        if not priced.lines:
            form.add_error(None, "Your cart is empty.")
        if form.is_valid():
            return _place_order(request, form, addresses)
    else:
        form = CheckoutForm(addresses=addresses, initial=_default_initial(request, addresses))

    context.update(
        {
            "form": form,
            "addresses": addresses,
            "terms": settings.CHECKOUT_TERMS_TEXT,
            "config_dispatch": settings.DISPATCH_DAYS,
            "config_delivery": settings.DELIVERY_DAYS,
        }
    )
    return render(request, "checkout/page.html", context)


def _default_initial(request, addresses) -> dict:
    """Prefill the phone and preselect the default saved address, so a returning customer
    with a saved address can pay in one tap."""
    initial = {"phone": request.user.phone}
    default = next((a for a in addresses if a.is_default), None) or (
        addresses[0] if addresses else None
    )
    if default:
        initial["saved_address"] = str(default.id)
    return initial


def _shipping_from_form(request, form, addresses) -> dict:
    """The address the order snapshots: a picked saved one, or the typed new one."""
    data = form.cleaned_data
    picked_id = data.get("saved_address")
    if picked_id:
        address = next((a for a in addresses if str(a.id) == picked_id), None)
        if address is not None:
            return {
                "full_name": address.full_name,
                "phone": data["phone"] or address.phone,
                "line1": address.line1,
                "line2": address.line2,
                "city": address.city,
                "state": address.state,
                "postal_code": address.postal_code,
                "country": address.country,
            }
    return {
        "full_name": data["full_name"],
        "phone": data["phone"],
        "line1": data["line1"],
        "line2": data["line2"],
        "city": data["city"],
        "state": data["state"],
        "postal_code": data["postal_code"],
        "country": "IN",
    }


def _place_order(request, form, addresses):
    shipping = _shipping_from_form(request, form, addresses)
    cart = cart_services.get_or_create_cart(request)
    try:
        order = services.create_order_from_cart(
            request.user, cart, shipping, rights_ack_text=settings.CHECKOUT_TERMS_TEXT
        )
    except services.OrderError as exc:
        form.add_error(None, exc.message)
        return None

    if form.cleaned_data.get("save_address") and not form.cleaned_data.get("saved_address"):
        CheckoutView._save_address(request.user, shipping)

    try:
        payment_services.create_gateway_order(order)
    except payment_gateway.PaymentError as exc:
        services.transition(order, Order.Status.CANCELLED)
        form.add_error(None, exc.message)
        return None

    return redirect("checkout-pay", order_number=order.order_number)


@login_required
def checkout_pay(request, order_number):
    """The Razorpay handoff page for a still-pending order. Reads the order's open gateway
    order and hands the browser what it needs to launch the hosted checkout modal. Owner-scoped
    and read-only; it never mutates order state."""
    order = get_object_or_404(
        Order.objects.filter(user=request.user, status=Order.Status.PAYMENT_PENDING),
        order_number=order_number,
    )
    payment = order.payments.order_by("-created_at").first()
    if payment is None:
        return redirect("checkout-page")
    return render(
        request,
        "checkout/pay.html",
        {
            "order": order,
            "razorpay_key_id": settings.RAZORPAY_KEY_ID,
            "razorpay_order_id": payment.gateway_order_id,
            "amount_paise": payment_gateway.to_paise(order.total),
        },
    )


@login_required
def checkout_thank_you(request, order_number):
    """Order confirmation, keyed on the order number. Owner-scoped, read-only and reload-safe:
    it reflects whatever the webhook has done, showing "confirming" while the order is still
    pending and "confirmed" once paid. Bookmarking or refreshing it changes nothing."""
    order = get_object_or_404(
        Order.objects.filter(user=request.user).prefetch_related("items"),
        order_number=order_number,
    )
    return render(request, "checkout/thank_you.html", {"order": order, "priced": None})


@login_required
def account_orders(request):
    orders = Order.objects.filter(user=request.user).prefetch_related("items")
    return render(request, "account/orders.html", {"orders": orders})


@login_required
def account_order_detail(request, order_number):
    order = get_object_or_404(
        Order.objects.filter(user=request.user).prefetch_related(
            "items", "shipments__items", "status_events"
        ),
        order_number=order_number,
    )
    if request.method == "POST" and request.POST.get("action") == "cancel":
        try:
            services.customer_cancel(order)
            messages.success(request, "Your order has been cancelled.")
        except services.OrderError as exc:
            messages.error(request, exc.message)
        return redirect("account-order-detail", order_number=order_number)

    return render(
        request,
        "account/order_detail.html",
        {
            "order": order,
            "can_cancel": services.can_customer_cancel(order),
            "can_retry": order.status == Order.Status.PAYMENT_PENDING and order.payments.exists(),
            "source_labels": {
                "stock": "Shipped by CivicForest",
                "custom": "Printed and shipped by Qikink",
            },
        },
    )


def track_order(request):
    """Guest order tracking (I2): look up an order by its public number and the email it was
    placed with, no login. Rate-limited per IP so it can't be ground into an enumeration oracle,
    and it reveals nothing on a miss beyond "not found"."""
    order = None
    error = ""
    if request.method == "POST":
        if exceeded(request, TrackThrottle):
            error = "Too many attempts. Please wait a minute and try again."
        else:
            number = request.POST.get("order_number", "").strip()
            email = request.POST.get("email", "").strip()
            order = (
                Order.objects.filter(order_number__iexact=number, email__iexact=email)
                .prefetch_related("shipments__items")
                .first()
            )
            if order is None:
                error = "No order matches that number and email."
    return render(
        request,
        "track/track.html",
        {
            "order": order,
            "error": error,
            "source_labels": {
                "stock": "Shipped by CivicForest",
                "custom": "Printed and shipped by Qikink",
            },
        },
    )


class OrderViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """Read-only list/detail of the authenticated user's orders."""

    serializer_class = OrderSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = "order_number"

    def get_queryset(self):
        return (
            Order.objects.filter(user=self.request.user)
            .prefetch_related("items")
            .order_by("-created_at")
        )


class CheckoutView(APIView):
    """Create an order from the current cart and open a Razorpay order for it."""

    permission_classes = [IsAuthenticated]
    throttle_classes = [CheckoutMinuteThrottle, CheckoutDayThrottle]

    def post(self, request):
        checkout_key = request.headers.get("X-Idempotency-Key")
        if checkout_key and not _CHECKOUT_KEY_RE.fullmatch(checkout_key):
            return Response(
                {
                    "error": {
                        "code": "invalid_idempotency_key",
                        "message": "X-Idempotency-Key must be 8-64 letters, digits, _ or -.",
                        "details": {},
                    }
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if checkout_key:
            existing = (
                Order.objects.filter(
                    user=request.user,
                    checkout_key=checkout_key,
                    status=Order.Status.PAYMENT_PENDING,
                )
                .prefetch_related("payments")
                .first()
            )
            if existing:
                payment = existing.payments.first()
                if payment:
                    return Response(
                        self._payment_payload(existing, payment), status=status.HTTP_200_OK
                    )
                try:
                    payment = payment_services.create_gateway_order(existing)
                except payment_gateway.PaymentError as exc:
                    return Response(
                        {"error": {"code": exc.code, "message": exc.message, "details": {}}},
                        status=status.HTTP_502_BAD_GATEWAY,
                    )
                return Response(self._payment_payload(existing, payment), status=status.HTTP_200_OK)

        serializer = CheckoutSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        shipping = serializer.validated_data["shipping_address"]

        cart = cart_services.get_or_create_cart(request)
        try:
            order = services.create_order_from_cart(
                request.user,
                cart,
                shipping,
                checkout_key=checkout_key,
                rights_ack_text=settings.CHECKOUT_TERMS_TEXT,
            )
        except services.OrderError as exc:
            return Response(
                {"error": {"code": exc.code, "message": exc.message, "details": {}}},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if serializer.validated_data.get("save_address"):
            self._save_address(request.user, shipping)

        try:
            payment = payment_services.create_gateway_order(order)
        except payment_gateway.PaymentError as exc:
            # Roll the order back to a cancellable state so it isn't stuck pending.
            services.transition(order, Order.Status.CANCELLED)
            return Response(
                {"error": {"code": exc.code, "message": exc.message, "details": {}}},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        return Response(
            self._payment_payload(order, payment),
            status=status.HTTP_201_CREATED,
        )

    @staticmethod
    def _payment_payload(order, payment):
        return {
            "order_number": order.order_number,
            "razorpay_order_id": payment.gateway_order_id,
            "razorpay_key_id": settings.RAZORPAY_KEY_ID,
            "amount": str(order.total),
            "amount_paise": payment_gateway.to_paise(order.total),
            "currency": order.currency,
        }

    @staticmethod
    def _save_address(user, shipping):
        from apps.accounts.models import Address

        Address.objects.get_or_create(
            user=user,
            line1=shipping["line1"],
            postal_code=shipping["postal_code"],
            defaults={
                "full_name": shipping["full_name"],
                "phone": shipping["phone"],
                "line2": shipping.get("line2", ""),
                "city": shipping["city"],
                "state": shipping["state"],
                "country": shipping.get("country", "IN"),
            },
        )

from decimal import Decimal

import pytest
from django.test import override_settings
from rest_framework.test import APIClient

from apps.cart.models import Cart, CartItem, Coupon
from apps.orders import services as order_services
from apps.orders.models import Order
from apps.payments.models import Payment, WebhookEvent

from .conftest import capture_event, sign_body

pytestmark = pytest.mark.django_db

SHIPPING = {
    "full_name": "Test Buyer",
    "phone": "9999999999",
    "line1": "1 MG Road",
    "city": "Bengaluru",
    "state": "Karnataka",
    "postal_code": "560001",
    "country": "IN",
}


def _order_with_payment(user, variant, qty=1, coupon=None):
    cart = Cart.objects.create(user=user, coupon=coupon)
    CartItem.objects.create(cart=cart, variant=variant, quantity=qty)
    order = order_services.create_order_from_cart(user, cart, SHIPPING)
    payment = Payment.objects.create(
        order=order,
        gateway_order_id="order_PAY1",
        amount=order.total,
        currency=order.currency,
    )
    return order, payment, cart


def _post_webhook(raw: bytes, sig: str):
    return APIClient().post(
        "/api/v1/payments/webhook/razorpay",
        data=raw,
        content_type="application/json",
        HTTP_X_RAZORPAY_SIGNATURE=sig,
    )


@override_settings(RAZORPAY_WEBHOOK_SECRET="whsec_test_secret")
def test_webhook_fulfils_order_and_decrements_stock(user, variant):
    order, _, cart = _order_with_payment(user, variant, qty=2)
    assert variant.stock_quantity == 3

    raw = capture_event("order_PAY1")
    resp = _post_webhook(raw, sign_body(raw))
    assert resp.status_code == 200
    assert resp.data["status"] == "fulfilled"

    order.refresh_from_db()
    variant.refresh_from_db()
    assert order.status == Order.Status.PAID
    assert variant.stock_quantity == 1  # 3 − 2
    assert cart.items.count() == 0  # cart cleared on payment


@override_settings(RAZORPAY_WEBHOOK_SECRET="whsec_test_secret")
def test_webhook_is_idempotent_on_replay(user, variant):
    order, _, _ = _order_with_payment(user, variant, qty=2)
    raw = capture_event("order_PAY1", event_id="evt_dup")

    first = _post_webhook(raw, sign_body(raw))
    second = _post_webhook(raw, sign_body(raw))

    assert first.data["status"] == "fulfilled"
    assert second.data["status"] == "duplicate"

    variant.refresh_from_db()
    assert variant.stock_quantity == 1  # decremented once, not twice
    assert WebhookEvent.objects.filter(event_id="evt_dup").count() == 1


@override_settings(RAZORPAY_WEBHOOK_SECRET="whsec_test_secret")
def test_webhook_rejects_bad_signature(user, variant):
    order, _, _ = _order_with_payment(user, variant, qty=1)
    raw = capture_event("order_PAY1")
    resp = _post_webhook(raw, "not-a-real-signature")
    assert resp.status_code == 400
    order.refresh_from_db()
    assert order.status == Order.Status.PAYMENT_PENDING  # untouched


@override_settings(RAZORPAY_WEBHOOK_SECRET="whsec_test_secret")
def test_webhook_increments_coupon_usage(user, variant):
    coupon = Coupon.objects.create(
        code="SAVE10", discount_type="percent", value=Decimal("10"), max_uses=5
    )
    order, _, _ = _order_with_payment(user, variant, qty=1, coupon=coupon)
    raw = capture_event("order_PAY1", event_id="evt_coupon")
    _post_webhook(raw, sign_body(raw))

    coupon.refresh_from_db()
    assert coupon.used_count == 1

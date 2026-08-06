from decimal import Decimal

import pytest
from django.core.cache import cache
from django.test import override_settings

from apps.cart.models import Cart, CartItem
from apps.orders import services as order_services
from apps.orders.models import Order

from .conftest import SHIPPING

pytestmark = pytest.mark.django_db


def test_order_list_is_scoped_to_owner(auth_client, other_user, user, variant):
    # An order owned by someone else must never appear in my list (IDOR).
    cart = Cart.objects.create(user=other_user)
    CartItem.objects.create(cart=cart, variant=variant, quantity=1)
    others = order_services.create_order_from_cart(other_user, cart, SHIPPING)

    resp = auth_client.get("/api/v1/orders")
    assert resp.status_code == 200
    numbers = [o["order_number"] for o in resp.data["results"]]
    assert others.order_number not in numbers


def test_order_detail_of_another_user_is_404(auth_client, other_user, variant):
    cart = Cart.objects.create(user=other_user)
    CartItem.objects.create(cart=cart, variant=variant, quantity=1)
    others = order_services.create_order_from_cart(other_user, cart, SHIPPING)

    resp = auth_client.get(f"/api/v1/orders/{others.order_number}")
    assert resp.status_code == 404


def test_checkout_creates_order_and_gateway_order(auth_client, user, variant, monkeypatch):
    # Add to cart via the API so the checkout reads the same session/user cart.
    auth_client.post("/api/v1/cart/items", {"variant_id": str(variant.id), "quantity": 2})

    # Mock the outbound Razorpay call — no network in tests.
    from apps.payments import gateway

    monkeypatch.setattr(gateway, "create_order", lambda amount, **kw: {"id": "order_TEST123"})
    monkeypatch.setattr("django.conf.settings.RAZORPAY_KEY_ID", "rzp_test_key", raising=False)

    resp = auth_client.post("/api/v1/checkout", {"shipping_address": SHIPPING}, format="json")
    assert resp.status_code == 201
    assert resp.data["razorpay_order_id"] == "order_TEST123"
    assert Decimal(resp.data["amount"]) == Decimal("1600.00")
    assert resp.data["amount_paise"] == 160000

    order = Order.objects.get(order_number=resp.data["order_number"])
    assert order.user == user
    assert order.status == Order.Status.PAYMENT_PENDING
    assert order.payments.filter(gateway_order_id="order_TEST123").exists()


def test_checkout_replays_existing_payment_for_same_key(auth_client, variant, monkeypatch):
    auth_client.post("/api/v1/cart/items", {"variant_id": str(variant.id), "quantity": 1})
    calls = []

    def create_gateway_order(amount, **kwargs):
        calls.append((amount, kwargs))
        return {"id": "order_IDEMPOTENT"}

    monkeypatch.setattr("apps.payments.gateway.create_order", create_gateway_order)
    monkeypatch.setattr("django.conf.settings.RAZORPAY_KEY_ID", "rzp_test_key", raising=False)
    headers = {"HTTP_X_IDEMPOTENCY_KEY": "checkout_key_123"}

    first = auth_client.post(
        "/api/v1/checkout", {"shipping_address": SHIPPING}, format="json", **headers
    )
    second = auth_client.post(
        "/api/v1/checkout", {"shipping_address": SHIPPING}, format="json", **headers
    )

    assert first.status_code == 201
    assert second.status_code == 200
    assert second.data == first.data
    assert len(calls) == 1
    assert Order.objects.filter(checkout_key="checkout_key_123").count() == 1
    order = Order.objects.get(checkout_key="checkout_key_123")
    assert order.payments.count() == 1


@pytest.mark.parametrize("key", ["short", "contains spaces", "x" * 65])
def test_checkout_rejects_invalid_idempotency_key(auth_client, key):
    response = auth_client.post(
        "/api/v1/checkout",
        {"shipping_address": SHIPPING},
        format="json",
        HTTP_X_IDEMPOTENCY_KEY=key,
    )

    assert response.status_code == 400
    assert response.data["error"]["code"] == "invalid_idempotency_key"
    assert Order.objects.count() == 0


@override_settings(
    REST_FRAMEWORK={
        "DEFAULT_THROTTLE_RATES": {
            "checkout": "10/min",
            "checkout_day": "60/day",
        }
    }
)
def test_checkout_throttles_eleventh_request(auth_client):
    cache.clear()
    try:
        for _ in range(10):
            response = auth_client.post(
                "/api/v1/checkout",
                {"shipping_address": SHIPPING},
                format="json",
            )
            assert response.status_code == 400  # empty cart, but request still consumed quota

        response = auth_client.post(
            "/api/v1/checkout", {"shipping_address": SHIPPING}, format="json"
        )
        assert response.status_code == 429
    finally:
        cache.clear()

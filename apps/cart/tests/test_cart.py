from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.test import override_settings
from django.utils import timezone

from apps.cart import services
from apps.cart.models import Cart, CartItem, Coupon

pytestmark = pytest.mark.django_db

User = get_user_model()


# ─── API: add / cap at stock ─────────────────────────────────────────────────
def test_add_item_returns_priced_cart(client, variant):
    resp = client.post("/api/v1/cart/items", {"variant_id": str(variant.id), "quantity": 2})
    assert resp.status_code == 201
    assert resp.data["item_count"] == 2
    # 2 × 800 = 1600; over the free-shipping threshold so shipping is 0.
    assert Decimal(resp.data["subtotal"]) == Decimal("1600.00")
    assert Decimal(resp.data["shipping"]) == Decimal("0.00")
    assert Decimal(resp.data["total"]) == Decimal("1600.00")


def test_add_item_cannot_exceed_stock(client, variant):
    resp = client.post("/api/v1/cart/items", {"variant_id": str(variant.id), "quantity": 6})
    assert resp.status_code == 400
    assert resp.data["error"]["code"] == "insufficient_stock"


def test_repeated_add_accumulates_but_caps_at_stock(client, variant):
    client.post("/api/v1/cart/items", {"variant_id": str(variant.id), "quantity": 3})
    resp = client.post("/api/v1/cart/items", {"variant_id": str(variant.id), "quantity": 3})
    # 3 + 3 = 6 > 5 in stock — rejected.
    assert resp.status_code == 400
    assert resp.data["error"]["code"] == "insufficient_stock"


def test_update_quantity_to_zero_removes_line(client, variant):
    client.post("/api/v1/cart/items", {"variant_id": str(variant.id), "quantity": 2})
    resp = client.patch(f"/api/v1/cart/items/{variant.id}", {"quantity": 0})
    assert resp.status_code == 200
    assert resp.data["item_count"] == 0


# ─── G7: ten of one item, wherever the request comes from ─────────────────────
def test_one_request_cannot_ask_for_more_than_ten(client, variant):
    resp = client.post("/api/v1/cart/items", {"variant_id": str(variant.id), "quantity": 11})
    assert resp.status_code == 400
    assert resp.data["error"]["code"] == "validation_error"
    assert "quantity" in resp.data["error"]["details"]


def test_repeated_adds_cannot_walk_past_ten(client, variant):
    # Stock is not the binding constraint here, the ten-per-line cap is.
    variant.stock_quantity = 50
    variant.save(update_fields=["stock_quantity"])

    client.post("/api/v1/cart/items", {"variant_id": str(variant.id), "quantity": 6})
    resp = client.post("/api/v1/cart/items", {"variant_id": str(variant.id), "quantity": 6})

    assert resp.status_code == 400
    assert resp.data["error"]["code"] == "max_quantity"
    assert resp.data["error"]["message"] == "You can order at most 10 of one item."


def test_a_negative_quantity_is_refused(client, variant):
    resp = client.post("/api/v1/cart/items", {"variant_id": str(variant.id), "quantity": -3})
    assert resp.status_code == 400
    assert resp.data["error"]["code"] == "validation_error"


# ─── Shipping rule ───────────────────────────────────────────────────────────
# Pinned rather than read from the environment, so the rule is under test and not a
# developer's .env.
@override_settings(SHIPPING_FLAT_RATE="79.00", FREE_SHIPPING_THRESHOLD="999.00")
def test_flat_shipping_applies_below_threshold(client, category):
    from apps.catalog.models import Product, ProductVariant

    cheap = Product.objects.create(
        name="Sticker", slug="sticker", category=category, base_price=Decimal("100.00")
    )
    v = ProductVariant.objects.create(
        product=cheap, size="OS", color="White", sku="STK-1", stock_quantity=10
    )
    resp = client.post("/api/v1/cart/items", {"variant_id": str(v.id), "quantity": 1})
    assert Decimal(resp.data["subtotal"]) == Decimal("100.00")
    assert Decimal(resp.data["shipping"]) == Decimal("79.00")
    assert Decimal(resp.data["total"]) == Decimal("179.00")


# ─── Coupons (server-side only) ──────────────────────────────────────────────
def test_percent_coupon_discounts_subtotal(client, variant):
    Coupon.objects.create(code="SAVE10", discount_type="percent", value=Decimal("10"))
    client.post("/api/v1/cart/items", {"variant_id": str(variant.id), "quantity": 2})
    resp = client.post("/api/v1/cart/coupon", {"code": "SAVE10"})
    assert resp.status_code == 200
    assert resp.data["coupon_code"] == "SAVE10"
    assert Decimal(resp.data["discount"]) == Decimal("160.00")  # 10% of 1600
    assert Decimal(resp.data["total"]) == Decimal("1440.00")


def test_expired_coupon_is_rejected(client, variant):
    Coupon.objects.create(
        code="OLD",
        discount_type="flat",
        value=Decimal("100"),
        expires_at=timezone.now() - timezone.timedelta(days=1),
    )
    client.post("/api/v1/cart/items", {"variant_id": str(variant.id), "quantity": 1})
    resp = client.post("/api/v1/cart/coupon", {"code": "OLD"})
    assert resp.status_code == 400
    assert resp.data["error"]["code"] == "coupon_invalid"


def test_coupon_below_min_order_value_is_rejected(client, variant):
    Coupon.objects.create(
        code="BIG", discount_type="flat", value=Decimal("100"), min_order_value=Decimal("5000")
    )
    client.post("/api/v1/cart/items", {"variant_id": str(variant.id), "quantity": 1})
    resp = client.post("/api/v1/cart/coupon", {"code": "BIG"})
    assert resp.status_code == 400


def test_maxed_out_coupon_is_rejected(client, variant):
    Coupon.objects.create(
        code="ONCE", discount_type="flat", value=Decimal("50"), max_uses=1, used_count=1
    )
    client.post("/api/v1/cart/items", {"variant_id": str(variant.id), "quantity": 1})
    resp = client.post("/api/v1/cart/coupon", {"code": "ONCE"})
    assert resp.status_code == 400


# ─── Guest → user merge on login ─────────────────────────────────────────────
def test_merge_guest_cart_sums_and_caps(variant):
    guest = Cart.objects.create(user=None, session_key="sess-abc")
    CartItem.objects.create(cart=guest, variant=variant, quantity=3)

    user = User.objects.create_user(email="buyer@example.com", password="pw-1234567!")
    user_cart = Cart.objects.create(user=user)
    CartItem.objects.create(cart=user_cart, variant=variant, quantity=4)

    services.merge_guest_cart_into_user("sess-abc", user)

    user_cart.refresh_from_db()
    line = user_cart.items.get(variant=variant)
    # 4 + 3 = 7, capped at stock of 5.
    assert line.quantity == 5
    assert not Cart.objects.filter(session_key="sess-abc", user__isnull=True).exists()


# ─── IDOR: a guest cart is never addressable by another session ──────────────
def test_separate_sessions_get_separate_carts(variant):
    from rest_framework.test import APIClient

    a, b = APIClient(), APIClient()
    a.post("/api/v1/cart/items", {"variant_id": str(variant.id), "quantity": 1})
    resp_b = b.get("/api/v1/cart")
    # B has its own empty cart — it cannot see A's item.
    assert resp_b.data["item_count"] == 0

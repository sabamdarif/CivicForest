"""What the JSON API refuses to take from a client (A13, Q1).

The endpoints exist to serve this site's own JavaScript, so the interesting tests are not the
happy paths but the payloads a tampered client would send: a total, a unit price, a discount, or
a coupon code guessed a hundred times.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from django.contrib.messages import get_messages
from django.core.cache import cache
from django.test import Client, override_settings
from rest_framework.test import APIClient

from apps.cart.models import Coupon
from apps.common.throttles import CouponThrottle

pytestmark = pytest.mark.django_db

PINNED = override_settings(SHIPPING_FLAT_RATE="79.00", FREE_SHIPPING_THRESHOLD="999.00")

THROTTLED = "Too many coupon attempts. Try again in a minute."


def _messages(response) -> list[str]:
    return [str(m) for m in get_messages(response.wsgi_request)]


@pytest.fixture
def tight_coupon_limit(monkeypatch):
    """Three attempts a minute instead of twenty, so the test need not make twenty.

    The rate is patched on the class rather than through settings, because DRF reads
    ``DEFAULT_THROTTLE_RATES`` once at import and ``override_settings`` would not reach it.
    """
    cache.clear()
    monkeypatch.setattr(CouponThrottle, "rate", "3/min", raising=False)
    yield
    cache.clear()


# ─── Money in a payload is never money in the cart ───────────────────────────
@PINNED
def test_money_in_the_payload_is_dropped_on_the_floor(client, variant):
    resp = client.post(
        "/api/v1/cart/items",
        {
            "variant_id": str(variant.id),
            "quantity": 2,
            "unit_price": "1.00",
            "line_total": "1.00",
            "subtotal": "1.00",
            "discount": "700.00",
            "shipping": "0.00",
            "tax": "0.00",
            "total": "1.00",
        },
    )

    assert resp.status_code == 201
    assert Decimal(resp.data["subtotal"]) == Decimal("1600.00")
    assert Decimal(resp.data["discount"]) == Decimal("0.00")
    assert Decimal(resp.data["total"]) == Decimal("1600.00")
    assert Decimal(resp.data["lines"][0]["unit_price"]) == Decimal("800.00")


def test_a_patched_unit_price_does_not_move_the_line(client, variant):
    client.post("/api/v1/cart/items", {"variant_id": str(variant.id), "quantity": 1})

    resp = client.patch(f"/api/v1/cart/items/{variant.id}", {"quantity": 2, "unit_price": "1.00"})

    assert Decimal(resp.data["lines"][0]["unit_price"]) == Decimal("800.00")
    assert Decimal(resp.data["total"]) == Decimal("1600.00")


def test_a_discount_cannot_be_asked_for_without_a_coupon(client, variant):
    resp = client.post("/api/v1/cart/coupon", {"code": "SAVE10", "discount": "500.00"})

    # No such coupon, so no discount, whatever the payload asked for.
    assert resp.status_code == 400
    assert resp.data["error"]["code"] == "coupon_invalid"


def test_the_reported_tax_is_inside_the_reported_total(client, variant):
    resp = client.post("/api/v1/cart/items", {"variant_id": str(variant.id), "quantity": 1})

    subtotal = Decimal(resp.data["subtotal"])
    discount = Decimal(resp.data["discount"])
    shipping = Decimal(resp.data["shipping"])

    assert Decimal(resp.data["total"]) == subtotal - discount + shipping
    assert Decimal("0") < Decimal(resp.data["tax"]) < subtotal


# ─── Coupon guessing, on both doors ──────────────────────────────────────────
def test_coupon_guessing_is_throttled_on_the_json_endpoint(variant, tight_coupon_limit):
    api = APIClient()
    api.post("/api/v1/cart/items", {"variant_id": str(variant.id), "quantity": 1})

    codes = ["WRONG1", "WRONG2", "WRONG3", "WRONG4"]
    statuses = [api.post("/api/v1/cart/coupon", {"code": code}).status_code for code in codes]

    # Three wrong guesses are answered, the fourth is refused outright.
    assert statuses[:3] == [400, 400, 400]
    assert statuses[3] == 429


def test_coupon_guessing_is_throttled_on_the_form_too(catalogue, tight_coupon_limit):
    # The form is the door a guesser would actually use, so throttling only the JSON endpoint
    # would leave the real one open.
    browser = Client()
    for code in ("WRONG1", "WRONG2", "WRONG3"):
        browser.post("/cart/coupon/", {"code": code})

    resp = browser.post("/cart/coupon/", {"code": "WRONG4"}, follow=True)

    assert THROTTLED in _messages(resp)


def test_dropping_a_coupon_is_not_a_guess(catalogue, tight_coupon_limit):
    Coupon.objects.create(code="REAL10", discount_type="percent", value=Decimal("10"))
    browser = Client()
    for _ in range(5):
        browser.post("/cart/coupon/", {"op": "remove"})

    resp = browser.post("/cart/coupon/", {"code": "REAL10"}, follow=True)

    # Clearing a code cannot be brute-forced, so it never spends an attempt.
    assert THROTTLED not in _messages(resp)

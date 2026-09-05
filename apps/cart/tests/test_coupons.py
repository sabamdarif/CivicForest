"""Every coupon rule J2 asks for, tested the way a customer would abuse it.

The rules that matter are the ones that used to be missing: a code with a start date, a
per-customer limit, a scope, and a sale exclusion. `test_cart.py` still owns the three that
already existed (expired, below the minimum, past the global cap).
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.test import override_settings
from django.utils import timezone

from apps.cart import services
from apps.cart.models import Cart, CartItem, Coupon, CouponRedemption
from apps.common.factories import (
    CategoryFactory,
    OrderFactory,
    ProductVariantFactory,
    UserFactory,
)
from apps.orders.models import Order

pytestmark = pytest.mark.django_db

PINNED = override_settings(SHIPPING_FLAT_RATE="79.00", FREE_SHIPPING_THRESHOLD="999.00")


def _cart(*lines, user=None) -> Cart:
    cart = Cart.objects.create(user=user, session_key="" if user else "sess-coupon")
    for variant, quantity in lines:
        CartItem.objects.create(cart=cart, variant=variant, quantity=quantity)
    return cart


def _coupon(**kwargs) -> Coupon:
    kwargs.setdefault("code", "SAVE10")
    kwargs.setdefault("discount_type", "percent")
    kwargs.setdefault("value", Decimal("10"))
    return Coupon.objects.create(**kwargs)


def _reason(coupon: Coupon, cart: Cart) -> str:
    priced = services.price_cart(cart)
    return services.check_coupon(coupon, cart, priced.subtotal, priced.lines)


# ─── Dates ───────────────────────────────────────────────────────────────────
def test_a_coupon_that_has_not_started_is_refused():
    cart = _cart((ProductVariantFactory(), 1))
    coupon = _coupon(starts_at=timezone.now() + timezone.timedelta(hours=1))

    assert _reason(coupon, cart) == "This coupon is not active yet."


def test_a_coupon_that_has_started_is_accepted():
    cart = _cart((ProductVariantFactory(), 1))
    coupon = _coupon(starts_at=timezone.now() - timezone.timedelta(hours=1))

    assert _reason(coupon, cart) == ""


# ─── Per-customer limit ──────────────────────────────────────────────────────
def test_a_customer_past_their_own_limit_is_refused():
    user = UserFactory()
    coupon = _coupon(per_user_limit=1)
    CouponRedemption.objects.create(coupon=coupon, user=user, order=OrderFactory(user=user))
    cart = _cart((ProductVariantFactory(), 1), user=user)

    assert _reason(coupon, cart) == "You have already used this coupon."


def test_a_customer_below_their_own_limit_is_accepted():
    user = UserFactory()
    coupon = _coupon(per_user_limit=2)
    CouponRedemption.objects.create(coupon=coupon, user=user, order=OrderFactory(user=user))

    assert _reason(coupon, _cart((ProductVariantFactory(), 1), user=user)) == ""


def test_another_customers_use_does_not_count_against_this_one():
    coupon = _coupon(per_user_limit=1)
    other = UserFactory()
    CouponRedemption.objects.create(coupon=coupon, user=other, order=OrderFactory(user=other))

    assert _reason(coupon, _cart((ProductVariantFactory(), 1), user=UserFactory())) == ""


def test_a_guest_cart_passes_the_per_user_limit_and_meets_it_at_checkout():
    # There is no customer to count yet. Decision 14 puts a login in front of checkout, which
    # is where the limit is enforced for real.
    coupon = _coupon(per_user_limit=1)

    assert _reason(coupon, _cart((ProductVariantFactory(), 1))) == ""


# ─── First order only ────────────────────────────────────────────────────────
def test_first_order_only_is_refused_once_the_customer_has_paid_for_something():
    user = UserFactory()
    OrderFactory(user=user, status=Order.Status.PAID)

    reason = _reason(_coupon(first_order_only=True), _cart((ProductVariantFactory(), 1), user=user))

    assert reason == "This coupon is for a first order only."


def test_an_unpaid_order_does_not_spend_the_first_order_coupon():
    user = UserFactory()
    OrderFactory(user=user, status=Order.Status.PAYMENT_PENDING)

    reason = _reason(_coupon(first_order_only=True), _cart((ProductVariantFactory(), 1), user=user))

    assert reason == ""


# ─── Scope ───────────────────────────────────────────────────────────────────
def test_a_scoped_coupon_does_not_apply_to_a_cart_it_does_not_cover():
    hoodies = CategoryFactory(name="Hoodies", slug="hoodies")
    coupon = _coupon()
    coupon.scope_categories.set([hoodies])

    reason = _reason(coupon, _cart((ProductVariantFactory(), 1)))

    assert reason == "This coupon does not apply to anything in your cart."


def test_a_scoped_category_covers_its_children():
    parent = CategoryFactory(name="T-Shirts", slug="t-shirts")
    child = CategoryFactory(name="Graphic Tees", slug="graphic-tees", parent=parent)
    coupon = _coupon()
    coupon.scope_categories.set([parent])
    variant = ProductVariantFactory(product__category=child, product__base_price=Decimal("1000"))

    cart = _cart((variant, 1))
    assert _reason(coupon, cart) == ""
    assert services.coupon_discount(coupon, services.price_cart(cart).lines) == Decimal("100.00")


def test_the_discount_is_taken_only_on_the_lines_in_scope():
    tees = CategoryFactory(name="T-Shirts", slug="t-shirts")
    hoodies = CategoryFactory(name="Hoodies", slug="hoodies")
    in_scope = ProductVariantFactory(product__category=tees, product__base_price=Decimal("1000"))
    out = ProductVariantFactory(product__category=hoodies, product__base_price=Decimal("2000"))
    coupon = _coupon()
    coupon.scope_categories.set([tees])

    cart = _cart((in_scope, 1), (out, 1))
    priced = services.price_cart(cart)

    # 10% of the 1000 line, not of the 3000 cart.
    assert services.coupon_discount(coupon, priced.lines) == Decimal("100.00")


def test_a_product_scope_reaches_past_the_category():
    coupon = _coupon()
    variant = ProductVariantFactory(product__base_price=Decimal("1000"))
    coupon.scope_products.set([variant.product])

    assert _reason(coupon, _cart((variant, 1))) == ""


# ─── Sale items ──────────────────────────────────────────────────────────────
def test_a_coupon_can_skip_a_line_that_is_already_discounted():
    full = ProductVariantFactory(product__base_price=Decimal("1000"))
    reduced = ProductVariantFactory(
        product__base_price=Decimal("800"), product__mrp=Decimal("1200")
    )
    coupon = _coupon(exclude_sale_items=True)

    priced = services.price_cart(_cart((full, 1), (reduced, 1)))

    # 10% of the full-price line only.
    assert services.coupon_discount(coupon, priced.lines) == Decimal("100.00")


def test_a_cart_of_nothing_but_sale_items_is_refused_with_a_reason():
    reduced = ProductVariantFactory(
        product__base_price=Decimal("800"), product__mrp=Decimal("1200")
    )
    coupon = _coupon(exclude_sale_items=True)

    reason = _reason(coupon, _cart((reduced, 1)))

    assert reason == "This coupon does not apply to anything in your cart."


# ─── Free shipping ───────────────────────────────────────────────────────────
@PINNED
def test_a_free_shipping_coupon_waives_the_fee_below_the_threshold():
    variant = ProductVariantFactory(product__base_price=Decimal("100"))
    cart = _cart((variant, 1))
    cart.coupon = _coupon(code="FREESHIP", value=Decimal("0"), free_shipping=True)
    cart.save(update_fields=["coupon"])

    priced = services.price_cart(cart)

    assert priced.discount == Decimal("0.00")
    assert priced.shipping == Decimal("0.00")
    assert priced.total == Decimal("100.00")


@PINNED
def test_free_shipping_stacks_with_an_amount_off_on_the_same_coupon():
    variant = ProductVariantFactory(product__base_price=Decimal("500"))
    cart = _cart((variant, 1))
    cart.coupon = _coupon(code="BOTH", value=Decimal("10"), free_shipping=True)
    cart.save(update_fields=["coupon"])

    priced = services.price_cart(cart)

    assert priced.discount == Decimal("50.00")
    assert priced.shipping == Decimal("0.00")
    assert priced.total == Decimal("450.00")


# ─── Applied, then the cart changes underneath it ────────────────────────────
def test_a_coupon_on_an_emptied_cart_discounts_nothing():
    variant = ProductVariantFactory()
    cart = _cart((variant, 1))
    cart.coupon = _coupon(discount_type="flat", value=Decimal("100"))
    cart.save(update_fields=["coupon"])
    cart.items.all().delete()

    priced = services.price_cart(cart)

    assert priced.coupon_code is None
    assert priced.discount == Decimal("0.00")
    assert priced.total == Decimal("0.00")


def test_a_coupon_that_expires_after_it_was_applied_stops_discounting():
    variant = ProductVariantFactory(product__base_price=Decimal("1000"))
    coupon = _coupon()
    cart = _cart((variant, 1))
    cart.coupon = coupon
    cart.save(update_fields=["coupon"])
    assert services.price_cart(cart).discount == Decimal("100.00")

    Coupon.objects.filter(pk=coupon.pk).update(
        expires_at=timezone.now() - timezone.timedelta(minutes=1)
    )
    cart.refresh_from_db()
    priced = services.price_cart(cart)

    # The cart still works; it just costs full price again.
    assert priced.discount == Decimal("0.00")
    assert priced.coupon_code is None
    assert priced.total == Decimal("1000.00")


def test_applying_a_second_coupon_replaces_the_first(client, variant):
    """H11: one coupon per order, which `Cart.coupon` being a single FK already guarantees."""
    _coupon(code="FIRST", value=Decimal("10"))
    _coupon(code="SECOND", value=Decimal("20"))
    client.post("/api/v1/cart/items", {"variant_id": str(variant.id), "quantity": 2})

    client.post("/api/v1/cart/coupon", {"code": "FIRST"})
    resp = client.post("/api/v1/cart/coupon", {"code": "SECOND"})

    assert resp.data["coupon_code"] == "SECOND"
    assert Decimal(resp.data["discount"]) == Decimal("320.00")  # 20% of 1600, not 30%


# ─── The admin cannot save a coupon that does nothing ────────────────────────
def test_a_coupon_with_no_effect_is_rejected():
    with pytest.raises(ValidationError):
        Coupon(code="NOTHING", discount_type="flat", value=Decimal("0")).full_clean()

    # The same coupon is fine once it waives shipping.
    Coupon(
        code="NOTHING", discount_type="flat", value=Decimal("0"), free_shipping=True
    ).full_clean()

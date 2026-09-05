"""Stock revalidation on a cart view (G9).

The cases are the ones that happen between adding a line and looking at it: someone else
bought the last one, a staff member deactivated the variant, or the product came down. Each
has to change the cart *and* say which line it changed, because a silent adjustment is how a
customer ends up disputing a total.
"""

from __future__ import annotations

import pytest

from apps.cart import services
from apps.cart.models import Cart, CartItem
from apps.common.factories import ProductVariantFactory

pytestmark = pytest.mark.django_db


def _cart_with(variant, quantity) -> Cart:
    cart = Cart.objects.create(user=None, session_key="sess-revalidate")
    CartItem.objects.create(cart=cart, variant=variant, quantity=quantity)
    return cart


def test_a_settled_cart_is_left_alone():
    cart = _cart_with(ProductVariantFactory(stock_quantity=5), 2)

    assert services.revalidate(cart) == []
    assert cart.items.get().quantity == 2


def test_a_line_is_reduced_to_what_is_left_and_says_so():
    variant = ProductVariantFactory(stock_quantity=5)
    cart = _cart_with(variant, 4)
    variant.stock_quantity = 2
    variant.save(update_fields=["stock_quantity"])

    changed = services.revalidate(cart)

    assert cart.items.get().quantity == 2
    assert len(changed) == 1
    assert variant.product.name in changed[0]
    assert "Only 2" in changed[0]


def test_a_sold_out_line_is_removed_and_named():
    variant = ProductVariantFactory(stock_quantity=3)
    cart = _cart_with(variant, 2)
    variant.stock_quantity = 0
    variant.save(update_fields=["stock_quantity"])

    changed = services.revalidate(cart)

    assert cart.items.count() == 0
    assert changed == [
        f"{variant.product.name}, M in Black has sold out, so we removed it from your cart."
    ]


def test_a_variant_deactivated_after_it_was_added_is_removed():
    variant = ProductVariantFactory(stock_quantity=5)
    cart = _cart_with(variant, 1)
    variant.is_active = False
    variant.save(update_fields=["is_active"])

    changed = services.revalidate(cart)

    assert cart.items.count() == 0
    assert "no longer available" in changed[0]


def test_a_product_taken_down_after_it_was_added_is_removed():
    variant = ProductVariantFactory(stock_quantity=5)
    cart = _cart_with(variant, 1)
    variant.product.is_active = False
    variant.product.save(update_fields=["is_active"])

    changed = services.revalidate(cart)

    assert cart.items.count() == 0
    assert "no longer available" in changed[0]


def test_a_line_left_over_the_cap_is_brought_back_to_ten():
    # Rows predating G7's cap, or written straight to the database, are repaired rather than
    # priced as they stand.
    variant = ProductVariantFactory(stock_quantity=50)
    cart = Cart.objects.create(user=None, session_key="sess-legacy")
    CartItem.objects.create(cart=cart, variant=variant, quantity=12)

    changed = services.revalidate(cart)

    assert cart.items.get().quantity == 10
    assert "Only 10" in changed[0]


def test_clearing_a_cart_drops_the_coupon_with_the_lines():
    from decimal import Decimal

    from apps.cart.models import Coupon

    cart = _cart_with(ProductVariantFactory(stock_quantity=5), 1)
    cart.coupon = Coupon.objects.create(code="SAVE10", discount_type="percent", value=Decimal("10"))
    cart.save(update_fields=["coupon"])

    services.clear(cart)

    cart.refresh_from_db()
    assert cart.items.count() == 0
    assert cart.coupon_id is None

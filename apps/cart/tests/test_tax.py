"""GST is extracted from a tax-inclusive price, never added to it (C3, J9).

The cases worth having are the ones where a rounding or apportionment mistake would be
invisible on a single-line cart: two rates in one cart, a coupon that moves the taxable value,
and freight that has to carry the rate of the goods it is delivering.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from django.test import override_settings

from apps.cart import services
from apps.cart.models import Cart, CartItem, Coupon
from apps.common.factories import ProductVariantFactory

pytestmark = pytest.mark.django_db

PINNED = override_settings(SHIPPING_FLAT_RATE="79.00", FREE_SHIPPING_THRESHOLD="999.00")


def _cart(*lines) -> Cart:
    """A guest cart holding (variant, quantity) pairs."""
    cart = Cart.objects.create(user=None, session_key="sess-tax")
    for variant, quantity in lines:
        CartItem.objects.create(cart=cart, variant=variant, quantity=quantity)
    return cart


def _variant(price, rate, stock=50):
    return ProductVariantFactory(
        product__base_price=Decimal(price),
        product__tax_rate=Decimal(rate),
        stock_quantity=stock,
    )


def test_the_tax_is_inside_the_total_not_on_top_of_it():
    priced = services.price_cart(_cart((_variant("800", "5"), 2)))

    assert priced.subtotal == Decimal("1600.00")
    assert priced.total == Decimal("1600.00")
    # 1600 × 5 / 105. The total is untouched: adding tax at checkout is drip pricing.
    assert priced.tax == Decimal("76.19")
    assert priced.total == priced.subtotal - priced.discount + priced.shipping


def test_each_line_carries_its_own_rate():
    tee = _variant("800", "5")
    hoodie = _variant("1499", "12")

    priced = services.price_cart(_cart((tee, 1), (hoodie, 1)))

    rates = {line.variant.id: line.tax_rate for line in priced.lines}
    assert rates == {tee.id: Decimal("5.00"), hoodie.id: Decimal("12.00")}
    taxes = {line.variant.id: line.tax for line in priced.lines}
    assert taxes == {tee.id: Decimal("38.10"), hoodie.id: Decimal("160.61")}
    assert priced.tax == Decimal("198.71")


@PINNED
def test_freight_is_taxed_at_the_rate_of_the_goods_it_carries():
    # 100 + 79 shipping, all of it at 5%: 179 × 5 / 105.
    priced = services.price_cart(_cart((_variant("100", "5"), 1)))

    assert priced.shipping == Decimal("79.00")
    assert priced.total == Decimal("179.00")
    assert priced.tax == Decimal("8.52")


def test_a_coupon_lowers_the_taxable_value():
    variant = _variant("800", "5")
    coupon = Coupon.objects.create(code="SAVE10", discount_type="percent", value=Decimal("10"))
    cart = _cart((variant, 2))
    cart.coupon = coupon
    cart.save(update_fields=["coupon"])

    priced = services.price_cart(cart)

    assert priced.discount == Decimal("160.00")
    # 1440 × 5 / 105, not 1600 × 5 / 105: a discount shown on the invoice comes off the
    # taxable value (CGST s.15(3)(a)).
    assert priced.tax == Decimal("68.57")


@PINNED
def test_the_taxable_values_add_back_up_to_the_total():
    cart = _cart((_variant("100", "5"), 1), (_variant("200", "12"), 1))
    cart.coupon = Coupon.objects.create(code="OFF50", discount_type="flat", value=Decimal("50"))
    cart.save(update_fields=["coupon"])

    priced = services.price_cart(cart)

    assert priced.total == Decimal("329.00")  # 300 - 50 + 79
    assert priced.tax == sum(line.tax for line in priced.lines)
    assert priced.tax == Decimal("28.72")


def test_an_empty_cart_owes_no_tax():
    priced = services.price_cart(_cart())

    assert priced.lines == []
    assert priced.tax == Decimal("0.00")
    assert priced.total == Decimal("0.00")


def test_a_zero_rated_product_owes_no_tax():
    priced = services.price_cart(_cart((_variant("500", "0"), 1)))

    assert priced.tax == Decimal("0.00")
    assert priced.lines[0].tax_rate == Decimal("0.00")


def test_apportioning_loses_no_paise():
    """Three equal lines splitting ₹10 must still sum to ₹10, not ₹9.99."""
    shares = services._apportion(Decimal("10.00"), [Decimal("1")] * 3)

    assert shares == [Decimal("3.33"), Decimal("3.33"), Decimal("3.34")]
    assert sum(shares) == Decimal("10.00")


def test_apportioning_an_empty_cart_is_not_a_division_by_zero():
    assert services._apportion(Decimal("79.00"), []) == []
    assert services._apportion(Decimal("79.00"), [Decimal("0")]) == [Decimal("0.00")]


def test_the_api_reports_the_tax_it_computed(client, variant):
    resp = client.post("/api/v1/cart/items", {"variant_id": str(variant.id), "quantity": 2})

    assert resp.status_code == 201
    assert Decimal(resp.data["tax"]) == Decimal("76.19")
    assert Decimal(resp.data["total"]) == Decimal("1600.00")

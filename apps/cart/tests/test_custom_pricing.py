"""Custom-line pricing (M7): the print surcharge is a server-side number.

A custom line's unit price is the blank variant's price plus the design's snapshotted
surcharge, recomputed by ``price_cart`` from the database. The client never sends a price, so
there is nothing to tamper: these tests pin the surcharge into the total and prove a stale
snapshot can't be edited by the customer."""

from decimal import Decimal

import pytest

from apps.cart.models import Cart, CartItem
from apps.cart.services import price_cart
from apps.custom_orders.models import CustomDesignOrder

pytestmark = pytest.mark.django_db


def _user(django_user_model):
    return django_user_model.objects.create_user(email="c@example.com", password="pw-1234567!")


def test_custom_line_adds_surcharge_to_the_total(variant, django_user_model):
    user = _user(django_user_model)
    design = CustomDesignOrder.objects.create(
        user=user, blank_variant=variant, print_surcharge=Decimal("199.00")
    )
    cart = Cart.objects.create(user=user)
    CartItem.objects.create(cart=cart, variant=variant, quantity=2, custom_design=design)

    priced = price_cart(cart)
    line = priced.lines[0]

    assert line.is_custom is True
    assert line.unit_price == Decimal("999.00")  # 800 blank + 199 surcharge
    assert line.line_total == Decimal("1998.00")
    assert priced.subtotal == Decimal("1998.00")


def test_two_designs_on_one_blank_are_two_lines(variant, django_user_model):
    """The variant-uniqueness constraint applies only to stock lines, so a customer can put
    two different designs on the same blank size and colour."""
    user = _user(django_user_model)
    cart = Cart.objects.create(user=user)
    for surcharge in ("99.00", "149.00"):
        design = CustomDesignOrder.objects.create(
            user=user, blank_variant=variant, print_surcharge=Decimal(surcharge)
        )
        CartItem.objects.create(cart=cart, variant=variant, quantity=1, custom_design=design)

    priced = price_cart(cart)
    assert len(priced.lines) == 2
    assert priced.subtotal == Decimal("1848.00")  # (800+99) + (800+149)

from decimal import Decimal

import pytest

from apps.cart.models import Cart, CartItem
from apps.orders import services
from apps.orders.models import Order

from .conftest import SHIPPING

pytestmark = pytest.mark.django_db


def _cart_with(user, variant, qty):
    cart = Cart.objects.create(user=user)
    CartItem.objects.create(cart=cart, variant=variant, quantity=qty)
    return cart


# ─── create_order_from_cart snapshots totals ─────────────────────────────────
def test_create_order_snapshots_totals(user, variant):
    cart = _cart_with(user, variant, 2)
    order = services.create_order_from_cart(user, cart, SHIPPING)

    assert order.status == Order.Status.PAYMENT_PENDING
    assert order.subtotal == Decimal("1600.00")
    assert order.total == Decimal("1600.00")  # over free-shipping threshold
    assert order.items.count() == 1
    item = order.items.get()
    assert item.unit_price == Decimal("800.00")
    assert item.quantity == 2
    assert item.variant_sku == "CBT-BLACK-M"


def test_order_number_is_non_sequential_and_prefixed(user, variant):
    o1 = services.create_order_from_cart(user, _cart_with(user, variant, 1), SHIPPING)
    assert o1.order_number.startswith("CF-")
    assert len(o1.order_number) == 11


def test_empty_cart_cannot_checkout(user):
    cart = Cart.objects.create(user=user)
    with pytest.raises(services.OrderError) as exc:
        services.create_order_from_cart(user, cart, SHIPPING)
    assert exc.value.code == "empty_cart"


# ─── State machine ───────────────────────────────────────────────────────────
def test_legal_transition_advances_status(user, variant):
    order = services.create_order_from_cart(user, _cart_with(user, variant, 1), SHIPPING)
    services.transition(order, Order.Status.PAID)
    services.transition(order, Order.Status.PROCESSING)
    services.transition(order, Order.Status.SHIPPED)
    assert order.status == Order.Status.SHIPPED


def test_illegal_transition_is_rejected(user, variant):
    order = services.create_order_from_cart(user, _cart_with(user, variant, 1), SHIPPING)
    # Cannot ship an order that hasn't been paid.
    with pytest.raises(services.OrderError) as exc:
        services.transition(order, Order.Status.SHIPPED)
    assert exc.value.code == "illegal_transition"


def test_transition_is_idempotent_to_same_state(user, variant):
    order = services.create_order_from_cart(user, _cart_with(user, variant, 1), SHIPPING)
    services.transition(order, Order.Status.PAYMENT_PENDING)  # no-op, no raise
    assert order.status == Order.Status.PAYMENT_PENDING


# ─── Stock reservation (row-lock guard) ──────────────────────────────────────
def test_two_orders_for_last_unit_only_one_reserves(user, other_user, variant):
    variant.stock_quantity = 1
    variant.save()
    order_a = services.create_order_from_cart(user, _cart_with(user, variant, 1), SHIPPING)
    order_b = services.create_order_from_cart(
        other_user, _cart_with(other_user, variant, 1), SHIPPING
    )

    services.reserve_stock(order_a)  # succeeds, stock → 0
    variant.refresh_from_db()
    assert variant.stock_quantity == 0

    with pytest.raises(services.InsufficientStock):
        services.reserve_stock(order_b)  # nothing left


def test_reserve_stock_is_all_or_nothing(user, variant):
    variant.stock_quantity = 5
    variant.save()
    order = services.create_order_from_cart(user, _cart_with(user, variant, 2), SHIPPING)
    services.reserve_stock(order)
    variant.refresh_from_db()
    assert variant.stock_quantity == 3

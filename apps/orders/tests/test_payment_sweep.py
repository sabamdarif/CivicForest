"""The 24 h failed-payment sweep (task 8, I3): a pending order past the window is cancelled,
a fresh one is left alone, and no stock moves because a pending order never reserved any."""

import pytest
from django.utils import timezone

from apps.cart.models import Cart, CartItem
from apps.orders import services
from apps.orders.models import Order

from .conftest import SHIPPING

pytestmark = pytest.mark.django_db


def _pending_order(user, variant, age=None):
    cart, _ = Cart.objects.get_or_create(user=user)
    cart.items.all().delete()
    CartItem.objects.create(cart=cart, variant=variant, quantity=1)
    order = services.create_order_from_cart(user, cart, SHIPPING)
    if age is not None:
        Order.objects.filter(pk=order.pk).update(created_at=timezone.now() - age)
    return order


def test_sweep_cancels_only_orders_past_the_window(user, variant):
    stale = _pending_order(user, variant, age=services.PAYMENT_WINDOW + timezone.timedelta(hours=1))
    fresh = _pending_order(user, variant, age=timezone.timedelta(minutes=5))

    cancelled = services.cancel_stale_pending_orders(100)

    stale.refresh_from_db()
    fresh.refresh_from_db()
    assert cancelled == 1
    assert stale.status == Order.Status.CANCELLED
    assert stale.cancelled_at is not None
    assert fresh.status == Order.Status.PAYMENT_PENDING


def test_sweep_leaves_stock_untouched(user, variant):
    assert variant.stock_quantity == 3
    _pending_order(user, variant, age=services.PAYMENT_WINDOW + timezone.timedelta(hours=1))

    services.cancel_stale_pending_orders(100)

    variant.refresh_from_db()
    assert variant.stock_quantity == 3  # a pending order held no stock to release

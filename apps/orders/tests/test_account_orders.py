"""Customer order pages (task 11) and guest tracking (task 12): cancellation is allowed only
before anything ships and returns stock on a paid order, and tracking is a per-IP-limited
lookup that leaks nothing on a miss."""

import pytest
from django.test import Client
from django.utils import timezone

from apps.cart.models import Cart, CartItem
from apps.orders import services
from apps.orders.models import Order

from .conftest import SHIPPING

pytestmark = pytest.mark.django_db


def _order(user, variant, qty=1, paid=False):
    cart, _ = Cart.objects.get_or_create(user=user)
    cart.items.all().delete()
    CartItem.objects.create(cart=cart, variant=variant, quantity=qty)
    order = services.create_order_from_cart(user, cart, SHIPPING)
    if paid:
        services.fulfil_paid_order(order, cart=cart)
        order.refresh_from_db()
    return order


def test_pending_order_can_be_cancelled(user, variant):
    order = _order(user, variant)
    assert services.can_customer_cancel(order)
    services.customer_cancel(order)
    order.refresh_from_db()
    assert order.status == Order.Status.CANCELLED


def test_cancelling_a_paid_order_returns_stock(user, variant):
    order = _order(user, variant, qty=2, paid=True)
    variant.refresh_from_db()
    assert variant.stock_quantity == 1  # 3 - 2 reserved on payment

    services.customer_cancel(order)
    variant.refresh_from_db()
    assert variant.stock_quantity == 3  # released on cancel


def test_shipped_order_cannot_be_cancelled(user, variant):
    order = _order(user, variant, paid=True)
    shipment = order.shipments.first()
    shipment.shipped_at = timezone.now()
    shipment.save()
    services.recompute_order_status_from_shipments(order)
    order.refresh_from_db()

    assert not services.can_customer_cancel(order)
    with pytest.raises(services.OrderError):
        services.customer_cancel(order)


def test_guest_tracking_finds_order_by_number_and_email(user, variant):
    order = _order(user, variant)
    resp = Client().post("/track/", {"order_number": order.order_number, "email": user.email})
    assert resp.status_code == 200
    assert order.order_number.encode() in resp.content


def test_guest_tracking_reveals_nothing_on_a_miss(user, variant):
    _order(user, variant)
    resp = Client().post("/track/", {"order_number": "CF-NOPE", "email": "nobody@example.com"})
    assert resp.status_code == 200
    assert b"No order matches" in resp.content

"""Fulfilment fans a paid order out into shipments (architecture §6), status changes leave a
StatusEvent trail, and order status is derived from shipments rather than set by hand."""

import pytest

from apps.cart.models import Cart, CartItem
from apps.orders import services
from apps.orders.models import Order, Shipment, StatusEvent

pytestmark = pytest.mark.django_db

from .conftest import SHIPPING


def _paid_order(user, variant, qty=1):
    cart = Cart.objects.create(user=user)
    CartItem.objects.create(cart=cart, variant=variant, quantity=qty)
    order = services.create_order_from_cart(user, cart, SHIPPING)
    services.fulfil_paid_order(order, cart=cart)
    order.refresh_from_db()
    return order


def test_stock_order_gets_one_stock_shipment(user, variant):
    order = _paid_order(user, variant)
    shipments = list(order.shipments.all())
    assert len(shipments) == 1
    assert shipments[0].kind == Shipment.Kind.STOCK
    assert set(shipments[0].items.all()) == set(order.items.all())


def test_paid_transition_writes_status_event(user, variant):
    order = _paid_order(user, variant)
    events = list(order.status_events.all())
    assert any(
        e.from_status == Order.Status.PAYMENT_PENDING and e.to_status == Order.Status.PAID
        for e in events
    )


def test_status_derived_from_shipments(user, variant):
    from django.utils import timezone

    order = _paid_order(user, variant)
    shipment = order.shipments.first()

    shipment.shipped_at = timezone.now()
    shipment.save()
    services.recompute_order_status_from_shipments(order)
    order.refresh_from_db()
    assert order.status == Order.Status.SHIPPED

    shipment.delivered_at = timezone.now()
    shipment.save()
    services.recompute_order_status_from_shipments(order)
    order.refresh_from_db()
    assert order.status == Order.Status.DELIVERED


def test_refulfilment_does_not_duplicate_shipments(user, variant):
    order = _paid_order(user, variant)
    # A second call is a no-op (already paid), and even a direct re-run adds no shipment.
    services._create_shipments(order)
    assert order.shipments.count() == 1


def test_illegal_transition_writes_no_event(user, variant):
    order = _paid_order(user, variant)
    before = StatusEvent.objects.filter(order=order).count()
    with pytest.raises(services.OrderError):
        services.transition(order, Order.Status.CREATED)
    assert StatusEvent.objects.filter(order=order).count() == before

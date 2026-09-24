"""Order detail actions (M8.5): the per-action authz, the guarded transitions, staff cancel,
the refund money path, shipment updates and notes.

Each mutating action is gated by its own permission, so the adversarial cases here are a
view-only role blocked from every action, an illegal transition surfaced not forced, and a
refund that only moves status once the gateway accepts it.
"""

import pytest
from django.contrib.auth.models import Permission
from django.core import mail
from django.urls import reverse

from apps.common.factories import (
    OrderFactory,
    OrderItemFactory,
    ProductVariantFactory,
    StaffUserFactory,
    login_staff_with_mfa,
)
from apps.orders.models import Order, Shipment

pytestmark = pytest.mark.django_db


def _staff_with(client, *codenames):
    user = StaffUserFactory()
    for codename in codenames:
        user.user_permissions.add(Permission.objects.get(codename=codename))
    login_staff_with_mfa(client, user=user)
    return user


def _action_url(order):
    return reverse("backoffice:order_action", kwargs={"order_number": order.order_number})


def test_detail_requires_view_permission(client):
    order = OrderFactory()
    _staff_with(client)  # staff + MFA, no order permission

    url = reverse("backoffice:order_detail", kwargs={"order_number": order.order_number})
    assert client.get(url).status_code == 404


def test_detail_renders_for_viewer(client):
    order = OrderFactory(status=Order.Status.PAID)
    OrderItemFactory(order=order)
    _staff_with(client, "view_order")

    url = reverse("backoffice:order_detail", kwargs={"order_number": order.order_number})
    body = client.get(url).content.decode()

    assert order.order_number in body
    assert order.email in body


def test_view_only_role_cannot_transition(client):
    order = OrderFactory(status=Order.Status.PAID)
    _staff_with(client, "view_order")

    response = client.post(_action_url(order), {"action": "advance", "to_status": "processing"})

    assert response.status_code == 404
    order.refresh_from_db()
    assert order.status == Order.Status.PAID


def test_transition_advances_order(client):
    order = OrderFactory(status=Order.Status.PAID)
    _staff_with(client, "transition_order")

    client.post(_action_url(order), {"action": "advance", "to_status": "processing"})

    order.refresh_from_db()
    assert order.status == Order.Status.PROCESSING


def test_illegal_transition_is_reported_not_forced(client):
    order = OrderFactory(status=Order.Status.PAYMENT_PENDING)
    _staff_with(client, "transition_order")

    response = client.post(_action_url(order), {"action": "advance", "to_status": "delivered"})

    assert response.status_code == 302
    order.refresh_from_db()
    assert order.status == Order.Status.PAYMENT_PENDING


def test_staff_cancel_releases_stock(client):
    variant = ProductVariantFactory(stock_quantity=3)
    order = OrderFactory(status=Order.Status.PAID)
    OrderItemFactory(order=order, variant=variant, quantity=2)
    _staff_with(client, "transition_order")

    client.post(_action_url(order), {"action": "cancel", "reason": "duplicate"})

    order.refresh_from_db()
    variant.refresh_from_db()
    assert order.status == Order.Status.CANCELLED
    assert variant.stock_quantity == 5  # the two reserved units returned


def test_view_only_role_cannot_refund(client):
    order = OrderFactory(status=Order.Status.PAID)
    _staff_with(client, "view_order", "transition_order")  # not refund_order

    response = client.post(_action_url(order), {"action": "refund"})

    assert response.status_code == 404
    order.refresh_from_db()
    assert order.status == Order.Status.PAID


def test_refund_moves_to_refunded_and_emails(client):
    from apps.payments.models import Payment

    order = OrderFactory(status=Order.Status.PAID)
    Payment.objects.create(
        order=order,
        gateway_order_id="order_x",
        gateway_payment_id="pay_x",
        amount=order.total,
        status=Payment.Status.CAPTURED,
    )
    _staff_with(client, "refund_order")

    client.post(_action_url(order), {"action": "refund"})

    order.refresh_from_db()
    assert order.status == Order.Status.REFUNDED
    assert any("Refund" in m.subject for m in mail.outbox)


def test_refund_without_captured_payment_is_reported(client):
    order = OrderFactory(status=Order.Status.PAID)
    _staff_with(client, "refund_order")

    response = client.post(_action_url(order), {"action": "refund"})

    assert response.status_code == 302
    order.refresh_from_db()
    assert order.status == Order.Status.PAID  # nothing to refund, no status change


def test_shipment_update_marks_shipped_and_derives_status(client):
    order = OrderFactory(status=Order.Status.PAID)
    shipment = Shipment.objects.create(order=order, kind=Shipment.Kind.STOCK)
    _staff_with(client, "change_order")

    client.post(
        _action_url(order),
        {
            "action": "shipment",
            "shipment_id": str(shipment.id),
            "carrier": "Delhivery",
            "awb": "AWB123",
            "mark_shipped": "1",
        },
    )

    shipment.refresh_from_db()
    order.refresh_from_db()
    assert shipment.awb == "AWB123"
    assert shipment.shipped_at is not None
    assert order.status == Order.Status.SHIPPED


def test_note_is_added_to_the_timeline(client):
    order = OrderFactory(status=Order.Status.PAID)
    _staff_with(client, "change_order")

    client.post(_action_url(order), {"action": "note", "note": "called the customer"})

    event = order.status_events.get()
    assert event.note == "called the customer"
    assert event.from_status == event.to_status


def test_packing_slip_renders(client):
    order = OrderFactory(status=Order.Status.PAID)
    OrderItemFactory(order=order)
    _staff_with(client, "view_order")

    url = reverse("backoffice:order_packing_slip", kwargs={"order_number": order.order_number})
    body = client.get(url).content.decode()

    assert order.ship_full_name in body
    assert order.order_number in body

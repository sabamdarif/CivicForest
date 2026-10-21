"""The order queue (M8.4): the view gate, filters and saved views, streamed CSV, and the
bulk-status endpoint's authz and state-machine guards.

Money and authz paths earn adversarial tests: a view-only role cannot reach the bulk endpoint,
an illegal transition is skipped rather than forced, and a tampered id is dropped.
"""

import pytest
from django.contrib.auth.models import Permission
from django.http import StreamingHttpResponse
from django.urls import reverse

from apps.common.factories import OrderFactory, StaffUserFactory, login_staff_with_mfa
from apps.orders.models import Order

pytestmark = pytest.mark.django_db


def _staff_with(client, *codenames):
    """A gated staff user holding exactly the named order permissions (not a superuser)."""
    user = StaffUserFactory()
    for codename in codenames:
        user.user_permissions.add(Permission.objects.get(codename=codename))
    login_staff_with_mfa(client, user=user)
    return user


def test_queue_requires_view_permission(client):
    _staff_with(client)  # staff + MFA but no order permission

    assert client.get(reverse("backoffice:orders")).status_code == 404


def test_queue_lists_orders(client):
    order = OrderFactory(status=Order.Status.PAID)
    _staff_with(client, "view_order")

    body = client.get(reverse("backoffice:orders")).content.decode()

    assert order.order_number in body


def test_saved_view_awaiting_shows_only_paid_and_processing(client):
    paid = OrderFactory(status=Order.Status.PAID)
    pending = OrderFactory(status=Order.Status.PAYMENT_PENDING)
    _staff_with(client, "view_order")

    body = client.get(reverse("backoffice:orders"), {"view": "awaiting"}).content.decode()

    assert paid.order_number in body
    assert pending.order_number not in body


def test_status_filter_narrows(client):
    shipped = OrderFactory(status=Order.Status.SHIPPED)
    paid = OrderFactory(status=Order.Status.PAID)
    _staff_with(client, "view_order")

    body = client.get(reverse("backoffice:orders"), {"status": "shipped"}).content.decode()

    assert shipped.order_number in body
    assert paid.order_number not in body


def test_csv_export_streams_with_header(client):
    OrderFactory(status=Order.Status.PAID)
    _staff_with(client, "view_order")

    response = client.get(reverse("backoffice:orders"), {"export": "csv"})

    assert isinstance(response, StreamingHttpResponse)
    first_line = next(iter(response.streaming_content)).decode()
    assert first_line.startswith("order_number,")


def test_bulk_endpoint_rejects_view_only_role(client):
    order = OrderFactory(status=Order.Status.PAID)
    _staff_with(client, "view_order")  # no transition_order

    response = client.post(
        reverse("backoffice:order_bulk"), {"ids": [str(order.id)], "to_status": "processing"}
    )

    assert response.status_code == 404
    order.refresh_from_db()
    assert order.status == Order.Status.PAID


def test_bulk_moves_permitted_orders(client):
    order = OrderFactory(status=Order.Status.PAID)
    _staff_with(client, "transition_order")

    client.post(
        reverse("backoffice:order_bulk"), {"ids": [str(order.id)], "to_status": "processing"}
    )

    order.refresh_from_db()
    assert order.status == Order.Status.PROCESSING


def test_bulk_skips_illegal_transition(client):
    # payment_pending cannot jump to delivered: the state machine skips it, no exception.
    order = OrderFactory(status=Order.Status.PAYMENT_PENDING)
    _staff_with(client, "transition_order")

    response = client.post(
        reverse("backoffice:order_bulk"), {"ids": [str(order.id)], "to_status": "delivered"}
    )

    assert response.status_code == 302
    order.refresh_from_db()
    assert order.status == Order.Status.PAYMENT_PENDING


def test_bulk_ignores_a_tampered_id(client):
    _staff_with(client, "transition_order")

    response = client.post(
        reverse("backoffice:order_bulk"), {"ids": ["not-a-uuid"], "to_status": "processing"}
    )

    assert response.status_code == 302

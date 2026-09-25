"""Customers (M8.10, O8): the view gate, lifetime value, and the guarded block action.

Blocking touches a user row, so it is gated by ``change_user`` (Owner only); a view-only role
cannot reach it. Lifetime value counts only revenue-status orders.
"""

import pytest
from django.contrib.auth.models import Permission
from django.http import StreamingHttpResponse
from django.urls import reverse

from apps.common.factories import (
    OrderFactory,
    StaffUserFactory,
    UserFactory,
    login_staff_with_mfa,
)
from apps.orders.models import Order

pytestmark = pytest.mark.django_db


def _staff_with(client, *codenames):
    user = StaffUserFactory()
    for codename in codenames:
        user.user_permissions.add(Permission.objects.get(codename=codename))
    login_staff_with_mfa(client, user=user)
    return user


def test_list_requires_view_permission(client):
    _staff_with(client)
    assert client.get(reverse("backoffice:customers")).status_code == 404


def test_list_shows_a_customer(client):
    UserFactory(email="shopper@example.com")
    _staff_with(client, "view_user")
    assert "shopper@example.com" in client.get(reverse("backoffice:customers")).content.decode()


def test_detail_lifetime_value_counts_only_revenue_orders(client):
    buyer = UserFactory(email="loyal@example.com")
    OrderFactory(user=buyer, status=Order.Status.PAID, total="859.00")
    OrderFactory(user=buyer, status=Order.Status.PAID, total="859.00")
    OrderFactory(user=buyer, status=Order.Status.CANCELLED, total="500.00")  # excluded
    _staff_with(client, "view_user")

    body = client.get(
        reverse("backoffice:customer_detail", kwargs={"pk": buyer.pk})
    ).content.decode()

    assert "1,718" in body


def test_block_requires_change_permission(client):
    buyer = UserFactory(is_active=True)
    _staff_with(client, "view_user")

    response = client.post(
        reverse("backoffice:customer_action", kwargs={"pk": buyer.pk}), {"action": "block"}
    )

    assert response.status_code == 404
    buyer.refresh_from_db()
    assert buyer.is_active is True


def test_block_deactivates_without_deleting(client):
    buyer = UserFactory(is_active=True)
    _staff_with(client, "change_user")

    client.post(reverse("backoffice:customer_action", kwargs={"pk": buyer.pk}), {"action": "block"})

    buyer.refresh_from_db()
    assert buyer.is_active is False


def test_export_streams_with_header(client):
    UserFactory()
    _staff_with(client, "view_user")

    response = client.get(reverse("backoffice:customers"), {"export": "csv"})

    assert isinstance(response, StreamingHttpResponse)
    assert next(iter(response.streaming_content)).decode().startswith("email,")

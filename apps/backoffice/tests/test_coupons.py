"""Coupons (M8.9, O7): the view gates, guarded create/edit/retire, and the usage report.

A coupon moves money, so the authz paths are adversarial: a view-only role cannot create, edit or
retire, and retiring deactivates rather than deleting so the redemption history survives.
"""

import pytest
from django.contrib.auth.models import Permission
from django.urls import reverse

from apps.cart.models import Coupon, CouponRedemption
from apps.common.factories import (
    CouponFactory,
    OrderFactory,
    StaffUserFactory,
    UserFactory,
    login_staff_with_mfa,
)

pytestmark = pytest.mark.django_db


def _staff_with(client, *codenames):
    user = StaffUserFactory()
    for codename in codenames:
        user.user_permissions.add(Permission.objects.get(codename=codename))
    login_staff_with_mfa(client, user=user)
    return user


def test_list_requires_view_permission(client):
    _staff_with(client)
    assert client.get(reverse("backoffice:coupons")).status_code == 404


def test_list_shows_a_coupon(client):
    CouponFactory(code="WELCOME10")
    _staff_with(client, "view_coupon")
    assert "WELCOME10" in client.get(reverse("backoffice:coupons")).content.decode()


def test_create_requires_add_permission(client):
    _staff_with(client, "view_coupon")
    assert client.get(reverse("backoffice:coupon_new")).status_code == 404


def test_create_saves_a_coupon(client):
    _staff_with(client, "add_coupon")

    client.post(
        reverse("backoffice:coupon_new"),
        {
            "code": "save20",
            "discount_type": "percent",
            "value": "20",
            "min_order_value": "0",
            "is_active": "on",
        },
    )

    assert Coupon.objects.get(code="SAVE20").discount_type == "percent"


def test_retire_requires_change_permission(client):
    coupon = CouponFactory(is_active=True)
    _staff_with(client, "view_coupon")

    response = client.post(
        reverse("backoffice:coupon_action", kwargs={"pk": coupon.pk}), {"action": "retire"}
    )

    assert response.status_code == 404
    coupon.refresh_from_db()
    assert coupon.is_active is True


def test_retire_deactivates_without_deleting(client):
    coupon = CouponFactory(is_active=True)
    _staff_with(client, "change_coupon")

    client.post(reverse("backoffice:coupon_action", kwargs={"pk": coupon.pk}), {"action": "retire"})

    coupon.refresh_from_db()
    assert coupon.is_active is False
    assert Coupon.objects.filter(pk=coupon.pk).exists()


def test_report_shows_per_customer_usage(client):
    coupon = CouponFactory(code="LOYAL")
    buyer = UserFactory(email="buyer@example.com")
    order = OrderFactory(user=buyer, discount="80.00")
    CouponRedemption.objects.create(coupon=coupon, user=buyer, order=order)
    _staff_with(client, "view_coupon")

    body = client.get(
        reverse("backoffice:coupon_report", kwargs={"pk": coupon.pk})
    ).content.decode()

    assert "buyer@example.com" in body

"""The dashboard renders the O1 tiles and both SVG charts for a gated staff user."""

import pytest
from django.urls import reverse

from apps.common.factories import login_staff_with_mfa

pytestmark = pytest.mark.django_db


def test_requires_the_staff_gate(client):
    # A plain customer never sees it (the gate is covered in depth in test_access).
    assert client.get(reverse("backoffice:dashboard")).status_code == 404


def test_renders_every_tile_and_chart(client):
    login_staff_with_mfa(client)

    body = client.get(reverse("backoffice:dashboard")).content.decode()

    for label in (
        "Revenue today",
        "Revenue, 30 days",
        "Avg order value",
        "Units sold, 30 days",
        "New customers, 30 days",
        "Awaiting fulfilment",
        "Designs to review",
        "Failed Qikink jobs",
        "Failed payments, 30 days",
        "Abandoned carts",
        "Coupon uses, 30 days",
        "Zero-result searches, 30 days",
        "Conversion rate, 30 days",
    ):
        assert label in body, label
    assert "bo-chart--spark" in body
    assert "bo-chart--bars" in body


def test_conversion_rate_is_safe_with_no_carts(client):
    login_staff_with_mfa(client)

    # No orders and no carts: the tile must not divide by zero.
    assert "0.0%" in client.get(reverse("backoffice:dashboard")).content.decode()

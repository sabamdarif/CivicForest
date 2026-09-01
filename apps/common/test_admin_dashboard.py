from decimal import Decimal

import pytest
from django.template import engines

from apps.common.factories import OrderFactory
from apps.common.templatetags.admin_dashboard import admin_dashboard
from apps.orders.models import Order


@pytest.mark.django_db
def test_dashboard_counts_only_captured_revenue():
    OrderFactory(status=Order.Status.PAID, total=Decimal("500"))
    OrderFactory(status=Order.Status.DELIVERED, total=Decimal("250"))
    # Unpaid — must not count as sales.
    OrderFactory(status=Order.Status.PAYMENT_PENDING, total=Decimal("999"))

    ctx = admin_dashboard()

    assert ctx["tiles"][0] == ("Revenue, last 30 days", "₹750")
    assert len(ctx["series"]) == 30
    assert sum(d["revenue"] for d in ctx["series"]) == 750.0
    assert len(ctx["recent_orders"]) == 3


@pytest.mark.django_db
def test_admin_index_shows_dashboard(client, settings):
    from django.contrib.auth import get_user_model
    from django.urls import reverse

    settings.DEBUG = True  # dev convenience path: skips the staff-MFA gate
    admin_user = get_user_model().objects.create_superuser(
        email="admin@example.com", password="pw-1234567!"
    )
    client.force_login(admin_user)

    resp = client.get(reverse("admin:index"))

    assert resp.status_code == 200
    assert "Revenue — last 30 days" in resp.text
    assert "Recent actions" in resp.text  # stock index body still present


@pytest.mark.django_db
def test_dashboard_template_renders():
    OrderFactory(status=Order.Status.PAID, total=Decimal("500"))

    html = engines["django"].from_string("{% load admin_dashboard %}{% admin_dashboard %}").render()

    assert "Revenue — last 30 days" in html
    assert "cf-dash-data" in html

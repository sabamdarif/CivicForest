"""Order email (apps.common.email): content, recipients, failure handling."""

from __future__ import annotations

import pytest
from django.core import mail

from apps.common.email import send_order_email
from apps.common.factories import OrderFactory, OrderItemFactory

pytestmark = pytest.mark.django_db


@pytest.fixture
def order():
    order = OrderFactory(email="buyer@example.com")
    OrderItemFactory(order=order)
    return order


def test_confirmation_email_contents(order):
    result = send_order_email(str(order.pk), "confirmation")
    assert result == "sent"
    assert len(mail.outbox) == 1
    msg = mail.outbox[0]
    assert msg.to == ["buyer@example.com"]
    assert order.order_number in msg.subject
    assert "859.00" in msg.body  # snapshotted total, not recomputed


def test_shipped_email_includes_tracking_awb(order):
    from apps.custom_orders.models import CustomDesignOrder

    CustomDesignOrder.objects.create(
        user=order.user,
        order=order,
        blank_variant=order.items.first().variant,
        tracking_awb="AWB123456",
    )
    send_order_email(str(order.pk), "shipped")
    assert "AWB123456" in mail.outbox[0].body


def test_unknown_order_or_kind_skips(order):
    assert send_order_email("0" * 32, "confirmation") == "skipped"
    assert send_order_email(str(order.pk), "nonsense") == "skipped"
    assert mail.outbox == []


@pytest.mark.parametrize(
    "kind,marker",
    [
        ("payment_failed", "could not be completed"),
        ("cancelled", "cancelled"),
        ("refunded", "refund"),
    ],
)
def test_new_order_emails_send(order, kind, marker):
    assert send_order_email(str(order.pk), kind) == "sent"
    assert marker.lower() in (mail.outbox[0].subject + mail.outbox[0].body).lower()


def test_shipment_email_names_contents_and_awb(order):
    from apps.common.email import send_shipment_email
    from apps.orders.models import Shipment

    shipment = Shipment.objects.create(order=order, kind=Shipment.Kind.STOCK, awb="AWB99")
    shipment.items.set(order.items.all())
    assert send_shipment_email(str(shipment.pk), "shipped") == "sent"
    body = mail.outbox[0].body
    assert "AWB99" in body
    assert "CivicForest" in body


def test_smtp_failure_returns_failed_without_raising(order, monkeypatch):
    def boom(*a, **kw):
        raise OSError("smtp down")

    monkeypatch.setattr("apps.common.email.send_mail", boom)
    assert send_order_email(str(order.pk), "confirmation") == "failed"

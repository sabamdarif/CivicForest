"""Returns (M9.3): eligibility from the delivery window, the stock-vs-custom reason rule, the
no-JS request form, per-action back-office authz, and the partial refund that does not flip the
whole order. The photo path is asserted to store keys only, never bytes through Django.
"""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

import pytest
from django.contrib.auth.models import Permission
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from apps.common.factories import (
    OrderFactory,
    OrderItemFactory,
    StaffUserFactory,
    UserFactory,
    login_staff_with_mfa,
)
from apps.orders import services
from apps.orders.models import Order, ReturnRequest, Shipment
from apps.payments.models import Payment

pytestmark = pytest.mark.django_db


def _staff_with(client, *codenames):
    user = StaffUserFactory()
    for codename in codenames:
        user.user_permissions.add(Permission.objects.get(codename=codename))
    login_staff_with_mfa(client, user=user)
    return user


def _delivered_order(user=None, *, days_ago=1, is_custom=False, kind=Shipment.Kind.STOCK):
    user = user or UserFactory()
    order = OrderFactory(user=user, status=Order.Status.DELIVERED)
    item = OrderItemFactory(order=order, is_custom=is_custom)
    shipment = Shipment.objects.create(
        order=order, kind=kind, delivered_at=timezone.now() - timedelta(days=days_ago)
    )
    shipment.items.set([item])
    return order, item


# ── Eligibility ────────────────────────────────────────────────────────────────
def test_a_recently_delivered_line_is_returnable():
    order, item = _delivered_order(days_ago=2)
    assert services.can_request_return(order) is True
    assert item in services.returnable_items(order)


def test_a_line_outside_the_window_is_not_returnable():
    order, _ = _delivered_order(days_ago=10)
    assert services.can_request_return(order) is False


def test_an_undelivered_order_has_nothing_to_return():
    user = UserFactory()
    order = OrderFactory(user=user, status=Order.Status.PROCESSING)
    OrderItemFactory(order=order)
    assert services.can_request_return(order) is False


def test_a_line_already_in_a_live_return_is_not_offered_again():
    order, item = _delivered_order(days_ago=1)
    services.create_return_request(
        order, item_ids=[item.id], reason=ReturnRequest.Reason.CHANGED_MIND, comment=""
    )
    assert item not in services.returnable_items(order)


# ── The stock-vs-custom reason rule (F13) ───────────────────────────────────────
def test_a_stock_line_returns_for_any_reason():
    order, item = _delivered_order(days_ago=1)
    rr = services.create_return_request(
        order, item_ids=[item.id], reason=ReturnRequest.Reason.CHANGED_MIND, comment="too big"
    )
    assert rr.status == ReturnRequest.Status.REQUESTED


def test_a_custom_line_is_defect_only():
    order, item = _delivered_order(days_ago=1, is_custom=True, kind=Shipment.Kind.CUSTOM)
    with pytest.raises(services.OrderError) as exc:
        services.create_return_request(
            order, item_ids=[item.id], reason=ReturnRequest.Reason.CHANGED_MIND, comment=""
        )
    assert exc.value.code == "custom_defect_only"

    rr = services.create_return_request(
        order, item_ids=[item.id], reason=ReturnRequest.Reason.DEFECTIVE, comment="misprint"
    )
    assert rr.status == ReturnRequest.Status.REQUESTED


# ── The customer form works without JavaScript ──────────────────────────────────
def test_the_return_form_is_a_plain_post():
    user = UserFactory()
    order, item = _delivered_order(user, days_ago=1)
    client = Client()
    client.force_login(user)
    resp = client.post(
        reverse("account-order-return", kwargs={"order_number": order.order_number}),
        {"items": [str(item.id)], "reason": "changed_mind", "comment": "sizing"},
    )
    assert resp.status_code == 302
    rr = ReturnRequest.objects.get(order=order)
    assert list(rr.items.all()) == [item]
    assert rr.photo_keys == []  # no bytes and no photos went through Django


def test_a_return_cannot_be_opened_on_someone_elses_order():
    order, item = _delivered_order(days_ago=1)
    client = Client()
    client.force_login(UserFactory())
    resp = client.post(
        reverse("account-order-return", kwargs={"order_number": order.order_number}),
        {"items": [str(item.id)], "reason": "changed_mind"},
    )
    assert resp.status_code == 404
    assert not ReturnRequest.objects.filter(order=order).exists()


# ── The photo-url endpoint mints a key, never accepts bytes ──────────────────────
def test_the_photo_url_endpoint_returns_a_key_and_presigned_put():
    client = Client()
    client.force_login(UserFactory())
    resp = client.post(
        reverse("return-photo-url"),
        {"content_type": "image/png", "bytes": 2048},
        content_type="application/json",
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["key"].startswith("returns/raw/")
    assert body["method"] == "PUT" and body["upload_url"]


# ── Back-office: per-action authz and the partial refund ─────────────────────────
def _approved_return_with_payment():
    order, item = _delivered_order(days_ago=1)
    Payment.objects.create(
        order=order,
        gateway="razorpay",
        gateway_order_id="order_x",
        gateway_payment_id="pay_x",
        amount=order.total,
        currency="INR",
        status=Payment.Status.CAPTURED,
    )
    rr = services.create_return_request(
        order, item_ids=[item.id], reason=ReturnRequest.Reason.DEFECTIVE, comment=""
    )
    services.approve_return(rr)
    return order, rr


def test_a_view_only_role_cannot_refund_a_return():
    order, rr = _approved_return_with_payment()
    client = Client()
    _staff_with(client, "view_returnrequest", "change_returnrequest")  # not refund_order
    resp = client.post(
        reverse("backoffice:return_action", kwargs={"pk": rr.id}),
        {"action": "refund", "amount": "100.00"},
    )
    assert resp.status_code == 404
    rr.refresh_from_db()
    assert rr.status == ReturnRequest.Status.APPROVED


def test_the_refund_is_partial_and_leaves_the_order_delivered():
    order, rr = _approved_return_with_payment()
    client = Client()
    _staff_with(client, "view_returnrequest", "refund_order")
    resp = client.post(
        reverse("backoffice:return_action", kwargs={"pk": rr.id}),
        {"action": "refund", "amount": "500.00"},
    )
    assert resp.status_code == 302
    rr.refresh_from_db()
    order.refresh_from_db()
    assert rr.status == ReturnRequest.Status.REFUNDED
    assert rr.refund_amount == Decimal("500.00")
    assert order.status == Order.Status.DELIVERED  # partial return never flips the whole order

"""Qikink submission and polling (M7.7, M7.8).

Two things this pins down: submission is idempotent (a retry never places a second print job),
and a polled Qikink status flows through the custom *shipment*, never straight onto the order,
so a mixed stock+custom order is derived correctly (rebuild/03-architecture.md §6)."""

import pytest
from django.core.cache import cache
from django.test import override_settings

from apps.custom_orders import services
from apps.custom_orders.models import CustomDesignOrder, DesignUpload
from apps.custom_orders.qikink import QikinkClient
from apps.orders.models import Order, OrderItem, Shipment

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _clear_cache():
    cache.clear()
    yield
    cache.clear()


def _design(user, review=DesignUpload.ReviewStatus.AUTO_OK):
    return DesignUpload.objects.create(
        user=user,
        r2_key_print="designs/print/x.png",
        status=DesignUpload.Status.READY,
        review_status=review,
        width_px=2000,
        height_px=2000,
    )


def _custom(user, variant, order, review=DesignUpload.ReviewStatus.AUTO_OK):
    return CustomDesignOrder.objects.create(
        user=user, order=order, blank_variant=variant, design_upload=_design(user, review)
    )


def _custom_shipment(order):
    return Shipment.objects.create(order=order, kind=Shipment.Kind.CUSTOM)


# ─── Idempotency: a retried submit never creates a duplicate ─────────────────
def test_submit_is_idempotent(user, variant, paid_order, monkeypatch):
    custom = _custom(user, variant, paid_order)
    calls = []

    def fake_create(self, payload):
        calls.append(payload)
        return {"order_id": "QK123"}

    monkeypatch.setattr(QikinkClient, "create_order", fake_create)
    monkeypatch.setattr(QikinkClient, "_token", lambda self: "tok")

    assert services.submit_to_qikink(custom) == "submitted"
    custom.refresh_from_db()
    assert custom.qikink_order_id == "QK123"

    # Second call (task retry) must be a no-op: no second create_order.
    assert services.submit_to_qikink(custom) == "already_submitted"
    assert len(calls) == 1


def test_payload_types_and_order_number(user, variant, paid_order, monkeypatch):
    custom = _custom(user, variant, paid_order)
    captured = {}
    monkeypatch.setattr(
        QikinkClient, "create_order", lambda self, p: captured.update(p) or {"order_id": "QK1"}
    )
    monkeypatch.setattr(QikinkClient, "_token", lambda self: "tok")
    services.submit_to_qikink(custom)

    line = captured["line_items"][0]
    assert line["search_from_my_products"] == 0  # a number
    assert isinstance(line["quantity"], str) and isinstance(line["price"], str)
    assert isinstance(captured["total_order_value"], str)
    assert len(captured["order_number"]) <= 15


def test_flagged_design_never_submits(user, variant, paid_order, monkeypatch):
    custom = _custom(user, variant, paid_order, review=DesignUpload.ReviewStatus.FLAGGED)
    monkeypatch.setattr(
        QikinkClient, "create_order", lambda self, p: pytest.fail("must not submit")
    )
    assert services.submit_to_qikink(custom) == "not_submittable"


def test_submit_advances_order_to_processing(user, variant, paid_order, monkeypatch):
    custom = _custom(user, variant, paid_order)
    monkeypatch.setattr(QikinkClient, "create_order", lambda self, p: {"order_id": "QK9"})
    monkeypatch.setattr(QikinkClient, "_token", lambda self: "tok")
    services.submit_to_qikink(custom)
    paid_order.refresh_from_db()
    assert paid_order.status == Order.Status.PROCESSING


# ─── Token is fetched once and reused from cache ─────────────────────────────
@override_settings(
    QIKINK_CLIENT_ID="cid",
    QIKINK_CLIENT_SECRET="secret",
    QIKINK_BASE_URL="https://sandbox.qikink.com",
)
def test_token_is_cached_and_reused(monkeypatch):
    sends = []

    def fake_send(self, method, path, **kw):
        sends.append(path)
        if path == "/api/token":
            return {"Accesstoken": "TESTTOKEN"}
        return {"ok": True}

    monkeypatch.setattr(QikinkClient, "_send", fake_send)
    client = QikinkClient()

    assert client._token() == "TESTTOKEN"
    assert client._token() == "TESTTOKEN"  # served from cache
    assert sends.count("/api/token") == 1


# ─── Status flows through the custom shipment, not the order directly ────────
def test_in_transit_ships_the_custom_shipment(user, variant, paid_order):
    custom = _custom(user, variant, paid_order)
    shipment = _custom_shipment(paid_order)

    services.apply_status(custom, "In-Transit", awb="AWB123", link="https://track/1")

    shipment.refresh_from_db()
    paid_order.refresh_from_db()
    assert shipment.shipped_at is not None
    assert shipment.awb == "AWB123" and shipment.tracking_url == "https://track/1"
    assert paid_order.status == Order.Status.SHIPPED


def test_delivered_marks_shipment_and_order_delivered(user, variant, paid_order):
    custom = _custom(user, variant, paid_order)
    shipment = _custom_shipment(paid_order)

    services.apply_status(custom, "Delivered")

    shipment.refresh_from_db()
    paid_order.refresh_from_db()
    custom.refresh_from_db()
    assert shipment.delivered_at is not None
    assert paid_order.status == Order.Status.DELIVERED
    assert custom.submit_status == CustomDesignOrder.SubmitStatus.TERMINAL


def test_in_progress_status_touches_no_timestamp(user, variant, paid_order):
    custom = _custom(user, variant, paid_order)
    shipment = _custom_shipment(paid_order)

    services.apply_status(custom, "Printed")

    shipment.refresh_from_db()
    paid_order.refresh_from_db()
    assert shipment.shipped_at is None
    assert paid_order.status == Order.Status.PAID


def test_custom_poll_does_not_overship_a_mixed_order(user, variant, paid_order):
    """The §6 win: a custom shipment going in-transit must not ship the whole order while the
    stock shipment is still unshipped."""
    stock_item = OrderItem.objects.create(
        order=paid_order,
        variant=variant,
        product_name="Stock Tee",
        variant_sku="ST-1",
        unit_price=paid_order.total,
        quantity=1,
        line_total=paid_order.total,
    )
    Shipment.objects.create(order=paid_order, kind=Shipment.Kind.STOCK).items.set([stock_item])
    custom = _custom(user, variant, paid_order)
    _custom_shipment(paid_order)

    services.apply_status(custom, "In-Transit", awb="AWB9")

    paid_order.refresh_from_db()
    assert paid_order.status == Order.Status.PARTIALLY_SHIPPED


def test_apply_status_rejects_non_http_tracking_link(user, variant, paid_order):
    custom = _custom(user, variant, paid_order)
    _custom_shipment(paid_order)

    services.apply_status(custom, "Printed", link="javascript:alert(1)")

    custom.refresh_from_db()
    assert custom.tracking_link == ""

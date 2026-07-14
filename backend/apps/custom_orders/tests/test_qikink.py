import pytest
from django.core.cache import cache
from django.core.files.base import ContentFile
from django.test import override_settings

from apps.custom_orders import services
from apps.custom_orders.models import CustomDesignOrder
from apps.custom_orders.qikink import QikinkClient
from apps.orders.models import Order

from .conftest import make_png_bytes

pytestmark = pytest.mark.django_db


def _custom(user, variant, order, review=CustomDesignOrder.ReviewStatus.AUTO_OK):
    custom = CustomDesignOrder(
        user=user,
        order=order,
        variant=variant,
        review_status=review,
        submit_status=CustomDesignOrder.SubmitStatus.PENDING_PAYMENT,
    )
    custom.design_file.save("d.png", ContentFile(make_png_bytes()), save=False)
    custom.save()
    return custom


@pytest.fixture(autouse=True)
def _clear_cache():
    cache.clear()
    yield
    cache.clear()


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

    # Second call (task retry) must be a no-op — no second create_order.
    assert services.submit_to_qikink(custom) == "already_submitted"
    assert len(calls) == 1


def test_flagged_design_never_submits(user, variant, paid_order, monkeypatch):
    custom = _custom(user, variant, paid_order, review=CustomDesignOrder.ReviewStatus.FLAGGED)
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
    # Token endpoint hit exactly once despite two _token() calls.
    assert sends.count("/api/token") == 1


# ─── Status mapping: each Qikink status → expected internal order state ───────
@pytest.mark.parametrize(
    "qikink_status,expected",
    [
        ("Printed", Order.Status.PROCESSING),
        ("In-Transit", Order.Status.SHIPPED),
        ("Delivered", Order.Status.DELIVERED),
    ],
)
def test_apply_status_maps_to_order_state(user, variant, paid_order, qikink_status, expected):
    custom = _custom(user, variant, paid_order)
    # Order must already be processing before it can ship/deliver (legal chain).
    from apps.orders import services as order_services

    if expected in (Order.Status.SHIPPED, Order.Status.DELIVERED):
        order_services.transition(paid_order, Order.Status.PROCESSING)
    if expected == Order.Status.DELIVERED:
        order_services.transition(paid_order, Order.Status.SHIPPED)

    services.apply_status(custom, qikink_status, awb="AWB123")
    paid_order.refresh_from_db()
    custom.refresh_from_db()
    assert paid_order.status == expected
    assert custom.tracking_awb == "AWB123"


def test_delivered_marks_custom_terminal(user, variant, paid_order):
    from apps.orders import services as order_services

    order_services.transition(paid_order, Order.Status.PROCESSING)
    order_services.transition(paid_order, Order.Status.SHIPPED)
    custom = _custom(user, variant, paid_order)
    services.apply_status(custom, "Delivered")
    custom.refresh_from_db()
    assert custom.submit_status == CustomDesignOrder.SubmitStatus.TERMINAL

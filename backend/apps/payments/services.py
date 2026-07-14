"""Payment services: create a gateway order, verify the advisory callback, and process
the authoritative webhook.

The webhook handler is the only place an order becomes ``paid``. It is idempotent
(event-id dedup + an already-paid short-circuit) and drives fulfilment — stock
decrement under row locks, cart clear, and enqueuing the print job — inside a single
transaction (plan.md §9)."""

from __future__ import annotations

import logging

from django.utils import timezone

from apps.orders import services as order_services
from apps.orders.models import Order

from . import gateway
from .models import Payment, WebhookEvent

logger = logging.getLogger("payments")


def create_gateway_order(order: Order) -> Payment:
    """Ask Razorpay to create an order for the server-computed total, and record a
    ``Payment`` row. The amount comes from the order snapshot — never the client."""
    razorpay_order = gateway.create_order(
        order.total,
        currency=order.currency,
        receipt=order.order_number,
        notes={"order_number": order.order_number},
    )
    payment = Payment.objects.create(
        order=order,
        gateway="razorpay",
        gateway_order_id=razorpay_order["id"],
        amount=order.total,
        currency=order.currency,
        status=Payment.Status.CREATED,
    )
    return payment


def verify_callback(order_id: str, payment_id: str, signature: str) -> bool:
    """Verify the browser checkout callback. Advisory: it may mark the payment row as
    captured for UI feedback, but it does **not** fulfil the order — the webhook does."""
    if not gateway.verify_payment_signature(order_id, payment_id, signature):
        return False
    Payment.objects.filter(gateway_order_id=order_id).update(
        gateway_payment_id=payment_id,
        signature=signature,
        status=Payment.Status.CAPTURED,
        verified_at=timezone.now(),
    )
    return True


def process_webhook(raw_body: bytes, signature: str, event: dict) -> str:
    """Handle a verified Razorpay webhook. Returns a short status string for logging.

    Caller must have already verified the signature against ``raw_body``. This function
    owns dedup and fulfilment."""
    event_id = event.get("id") or event.get("event_id") or ""
    event_type = event.get("event", "")

    ledger, created = WebhookEvent.objects.get_or_create(
        gateway="razorpay",
        event_id=event_id,
        defaults={"event_type": event_type, "payload": _scrub(event)},
    )
    if not created and ledger.processed:
        return "duplicate"

    if event_type == "payment.captured":
        result = _handle_capture(event)
    else:
        result = "ignored"

    ledger.processed = True
    ledger.event_type = event_type
    ledger.save(update_fields=["processed", "event_type", "updated_at"])
    return result


def _handle_capture(event: dict) -> str:
    entity = (
        event.get("payload", {}).get("payment", {}).get("entity", {})
        if isinstance(event.get("payload"), dict)
        else {}
    )
    gateway_order_id = entity.get("order_id", "")
    gateway_payment_id = entity.get("id", "")

    payment = (
        Payment.objects.filter(gateway_order_id=gateway_order_id).select_related("order").first()
    )
    if payment is None:
        logger.warning("Webhook capture for unknown gateway order %s", gateway_order_id)
        return "unknown_order"

    payment.gateway_payment_id = gateway_payment_id
    payment.status = Payment.Status.CAPTURED
    payment.verified_at = timezone.now()
    payment.save(update_fields=["gateway_payment_id", "status", "verified_at", "updated_at"])

    order = payment.order
    cart = _cart_for(order.user)
    try:
        order_services.fulfil_paid_order(order, cart=cart)
    except order_services.InsufficientStock:
        # Money captured but stock gone (rare race). Leave the order for manual
        # refund/review and alert — don't silently drop it (plan.md §16).
        logger.error("Oversold on paid order %s — needs refund/review", order.order_number)
        return "oversold"

    _enqueue_post_payment(order)
    return "fulfilled"


def _cart_for(user):
    from apps.cart.models import Cart

    return Cart.objects.filter(user=user).first()


def _enqueue_post_payment(order: Order) -> None:
    """Kick off async work that must happen only after payment is confirmed: for custom
    items, the Qikink print submission. Imported lazily so payments doesn't hard-depend
    on custom_orders being installed/migrated yet."""
    if not hasattr(order, "custom_designs"):
        return
    try:
        from apps.custom_orders.tasks import submit_custom_order_to_qikink

        for custom in order.custom_designs.all():
            submit_custom_order_to_qikink.delay(str(custom.id))
    except Exception:  # noqa: BLE001 - custom_orders optional
        logger.debug("No custom-order submission enqueued for %s", order.order_number)


def _scrub(event: dict) -> dict:
    """Drop obviously sensitive fields before persisting the webhook payload for audit."""
    import copy

    safe = copy.deepcopy(event)
    try:
        entity = safe["payload"]["payment"]["entity"]
        for key in ("card", "card_id", "vpa", "email", "contact"):
            entity.pop(key, None)
    except (KeyError, TypeError):
        pass
    return safe

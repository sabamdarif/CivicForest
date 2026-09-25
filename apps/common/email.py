"""Transactional email: plain-text bodies built inline.

Order-level notices (confirmation, payment failed, cancelled, refunded) and per-shipment
notices (shipped and delivered, one per parcel) are sent from the order and shipment state
changes in ``orders.services`` and the shipment admin. A send failure is logged and swallowed,
never raised, so a dead mail server cannot fail a payment webhook. With ``EMAIL_HOST`` unset the
console backend prints them (dev/offline); set SMTP env vars to actually deliver.
"""

from __future__ import annotations

import logging

from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone

logger = logging.getLogger("email")


def _deliver(to: str, template: str, context: dict, subject: str, body: str) -> str:
    """Send one email and record it in the `OutboundEmail` ledger (M8.13), so the back-office can
    list and resend it. A send failure is recorded and swallowed, never raised, so a dead mail
    server cannot fail a payment webhook."""
    from apps.common.models import OutboundEmail

    record = OutboundEmail.objects.create(
        to=to, template=template, context=context, subject=subject
    )
    try:
        send_mail(subject, body, settings.DEFAULT_FROM_EMAIL, [to])
    except Exception as exc:  # noqa: BLE001
        OutboundEmail.objects.filter(pk=record.pk).update(
            status=OutboundEmail.Status.FAILED, error=str(exc)
        )
        logger.warning("Email %s to %s failed: %s", template, to, exc)
        return "failed"
    OutboundEmail.objects.filter(pk=record.pk).update(
        status=OutboundEmail.Status.SENT, sent_at=timezone.now()
    )
    return "sent"


def _order_confirmation(order) -> tuple[str, str]:
    lines = "\n".join(
        f"  {i.quantity} × {i.product_name} ({i.size}/{i.color}) — {order.currency} {i.line_total}"
        for i in order.items.all()
    )
    body = (
        f"Hi {order.ship_full_name},\n\n"
        f"Thanks for your order {order.order_number}. We've received your payment.\n\n"
        f"{lines}\n\n"
        f"Subtotal: {order.currency} {order.subtotal}\n"
        f"Discount: {order.currency} {order.discount}\n"
        f"Shipping: {order.currency} {order.shipping_fee}\n"
        f"Total:    {order.currency} {order.total}\n\n"
        f"We'll email you again when it ships.\n\n— CivicForest"
    )
    return f"Order {order.order_number} confirmed", body


def _order_shipped(order) -> tuple[str, str]:
    tracking = ""
    custom = order.custom_designs.first() if hasattr(order, "custom_designs") else None
    if custom and custom.tracking_awb:
        tracking = f"\nTracking (AWB): {custom.tracking_awb}"
        if custom.tracking_link:
            tracking += f"\n{custom.tracking_link}"
    body = (
        f"Hi {order.ship_full_name},\n\n"
        f"Good news — your order {order.order_number} is on its way.{tracking}\n\n"
        f"— CivicForest"
    )
    return f"Order {order.order_number} shipped", body


def _order_delivered(order) -> tuple[str, str]:
    body = (
        f"Hi {order.ship_full_name},\n\n"
        f"Your order {order.order_number} has been delivered. We hope you love it.\n\n"
        f"— CivicForest"
    )
    return f"Order {order.order_number} delivered", body


def _payment_failed(order) -> tuple[str, str]:
    body = (
        f"Hi {order.ship_full_name},\n\n"
        f"We couldn't confirm payment for order {order.order_number}, so it has been cancelled. "
        f"Nothing was charged. You're welcome to place the order again whenever you're ready.\n\n"
        f"Thanks,\nThe CivicForest team"
    )
    return f"Order {order.order_number} could not be completed", body


def _order_cancelled(order) -> tuple[str, str]:
    reason = f"\n\nReason: {order.cancel_reason}" if order.cancel_reason else ""
    body = (
        f"Hi {order.ship_full_name},\n\n"
        f"Your order {order.order_number} has been cancelled.{reason}\n\n"
        f"Any amount paid is refunded to the original payment method.\n\n"
        f"Thanks,\nThe CivicForest team"
    )
    return f"Order {order.order_number} cancelled", body


def _order_refunded(order) -> tuple[str, str]:
    body = (
        f"Hi {order.ship_full_name},\n\n"
        f"We've processed a refund of {order.currency} {order.total} for order "
        f"{order.order_number}. It should reach your account in 5 to 7 working days.\n\n"
        f"Thanks,\nThe CivicForest team"
    )
    return f"Refund processed for order {order.order_number}", body


_BUILDERS = {
    "confirmation": _order_confirmation,
    "shipped": _order_shipped,
    "delivered": _order_delivered,
    "payment_failed": _payment_failed,
    "cancelled": _order_cancelled,
    "refunded": _order_refunded,
}

# The order-level emails staff can resend from the back-office order detail (M8.5).
ORDER_EMAIL_KINDS = tuple(_BUILDERS)


def send_order_email(order_id: str, kind: str) -> str:
    """Render and send one order email. Called from ``orders.services``."""
    from apps.orders.models import Order

    order = Order.objects.filter(pk=order_id).first()
    if order is None or kind not in _BUILDERS:
        return "skipped"
    subject, body = _BUILDERS[kind](order)
    return _deliver(
        order.email, f"order:{kind}", {"order_id": str(order.pk), "kind": kind}, subject, body
    )


# ─── Per-shipment notices (M1: one shipped email per shipment, with its own AWB) ──
_SOURCE = {"stock": "Shipped by CivicForest", "custom": "Printed and shipped by Qikink"}


def send_shipment_email(shipment_id: str, kind: str) -> str:
    """One notice per shipment (a mixed order gets two), naming what's inside and its own AWB,
    so the two dispatches read as the separate parcels they are. ``kind`` is "shipped" or
    "delivered". A send failure is swallowed, like every other transactional mail here."""
    from apps.orders.models import Shipment

    shipment = Shipment.objects.filter(pk=shipment_id).select_related("order").first()
    if shipment is None or kind not in ("shipped", "delivered"):
        return "skipped"
    order = shipment.order
    contents = "\n".join(
        f"  {i.quantity} x {i.product_name} ({i.size}/{i.color})" for i in shipment.items.all()
    )
    source = _SOURCE.get(shipment.kind, "Shipped")
    if kind == "shipped":
        tracking = f"\nTracking (AWB): {shipment.awb}" if shipment.awb else ""
        if shipment.tracking_url:
            tracking += f"\n{shipment.tracking_url}"
        subject = f"Part of order {order.order_number} has shipped"
        body = (
            f"Hi {order.ship_full_name},\n\n{source}. On its way to you:\n\n{contents}{tracking}"
            f"\n\nThanks,\nThe CivicForest team"
        )
    else:
        subject = f"Part of order {order.order_number} was delivered"
        body = (
            f"Hi {order.ship_full_name},\n\nDelivered:\n\n{contents}\n\n"
            f"Thanks,\nThe CivicForest team"
        )
    return _deliver(
        order.email,
        f"shipment:{kind}",
        {"shipment_id": str(shipment_id), "kind": kind},
        subject,
        body,
    )


# ─── Design review notices (M7.6: the customer hears the moderation outcome either way) ──
def send_design_review_email(design_id: str, kind: str) -> str:
    """Tell the customer their custom artwork was approved or rejected. ``kind`` is "approved"
    or "rejected". Swallowed on failure, like every transactional mail here."""
    from apps.custom_orders.models import DesignUpload

    design = DesignUpload.objects.filter(pk=design_id).select_related("user").first()
    if design is None or design.user is None or kind not in ("approved", "rejected"):
        return "skipped"
    if kind == "approved":
        subject = "Your custom design was approved"
        body = (
            "Hi,\n\nGood news: your custom design passed review and is going into print. "
            "If it was part of a paid order, we have sent it to production.\n\n"
            "Thanks,\nThe CivicForest team"
        )
    else:
        reason = f" Reason: {design.review_reason}" if design.review_reason else ""
        subject = "Your custom design could not be printed"
        body = (
            f"Hi,\n\nWe were unable to approve your custom design for printing.{reason}\n\n"
            "If you were charged for it, we will refund that line. You are welcome to upload a "
            "different design.\n\nThanks,\nThe CivicForest team"
        )
    return _deliver(
        design.user.email,
        f"design:{kind}",
        {"design_id": str(design_id), "kind": kind},
        subject,
        body,
    )


def resend(email_id: str) -> str:
    """Re-render and re-send a ledgered email (M8.13). It re-runs the original sender from the
    stored ids, so the resend reflects live data and writes its own fresh ledger row."""
    from apps.common.models import OutboundEmail

    row = OutboundEmail.objects.filter(pk=email_id).first()
    if row is None:
        return "skipped"
    prefix, _, _ = row.template.partition(":")
    context = row.context or {}
    kind = context.get("kind", "")
    if prefix == "order" and context.get("order_id"):
        return send_order_email(context["order_id"], kind)
    if prefix == "shipment" and context.get("shipment_id"):
        return send_shipment_email(context["shipment_id"], kind)
    if prefix == "design" and context.get("design_id"):
        return send_design_review_email(context["design_id"], kind)
    return "skipped"

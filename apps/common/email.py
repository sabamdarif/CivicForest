"""Transactional email: plain-text bodies built inline.

Order emails are the only transactional mail we send (confirmation, shipping,
delivery), sent from the order state changes in ``orders.services``. A send failure is
logged and swallowed, never raised, so a dead mail server cannot fail a payment
webhook. With ``EMAIL_HOST`` unset the console backend prints them (dev/offline); set
SMTP env vars to actually deliver.
"""

from __future__ import annotations

import logging

from django.conf import settings
from django.core.mail import send_mail

logger = logging.getLogger("email")


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


_BUILDERS = {
    "confirmation": _order_confirmation,
    "shipped": _order_shipped,
    "delivered": _order_delivered,
}


def send_order_email(order_id: str, kind: str) -> str:
    """Render and send one order email. Called from ``orders.services``."""
    from apps.orders.models import Order

    order = Order.objects.filter(pk=order_id).first()
    if order is None or kind not in _BUILDERS:
        return "skipped"
    subject, body = _BUILDERS[kind](order)
    try:
        send_mail(subject, body, settings.DEFAULT_FROM_EMAIL, [order.email])
    # A dead mail server must not fail the caller, so every send error is swallowed.
    except Exception as exc:  # noqa: BLE001
        logger.warning("Order email %s/%s failed: %s", order.order_number, kind, exc)
        return "failed"
    return "sent"

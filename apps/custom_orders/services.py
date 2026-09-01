"""Custom-order services: build the Qikink payload, submit after payment, and map
Qikink's status vocabulary onto our order state machine.

Submission is idempotent: once ``qikink_order_id`` is set we never resubmit, so a
retried submission cannot create a duplicate print job (plan.md §8)."""

from __future__ import annotations

import logging
from urllib.parse import urlsplit

from django.utils import timezone

from apps.orders import services as order_services
from apps.orders.models import Order

from .models import CustomDesignOrder
from .qikink import QikinkClient, QikinkError

logger = logging.getLogger("custom_orders")

# Qikink status → our Order status. Poll only ever advances state; illegal/backward
# transitions are caught and ignored so a late "Printed" can't un-ship an order.
QIKINK_STATUS_MAP: dict[str, str] = {
    "On Hold": Order.Status.PROCESSING,
    "Live OOS": Order.Status.PROCESSING,
    "Live": Order.Status.PROCESSING,
    "To be Printed": Order.Status.PROCESSING,
    "Partially Picklisted": Order.Status.PROCESSING,
    "Printed": Order.Status.PROCESSING,
    "Manifested": Order.Status.PROCESSING,
    "In-Transit": Order.Status.SHIPPED,
    "Exception": Order.Status.SHIPPED,
    "Delivered": Order.Status.DELIVERED,
    "RTO Initiated": Order.Status.REFUNDED,
    "Returned": Order.Status.REFUNDED,
    "Cancelled": Order.Status.CANCELLED,
}

_TERMINAL_QIKINK = {"Delivered", "RTO Initiated", "Returned", "Cancelled"}


def design_link(custom: CustomDesignOrder) -> str:
    """A URL Qikink can fetch the art from. With an S3/R2 backend this is a short-lived
    signed URL; on local disk it's the media URL (production must use object storage —
    plan.md §8)."""
    return custom.design_file.url if custom.design_file else ""


def build_order_payload(custom: CustomDesignOrder) -> dict:
    """Assemble the Qikink ``order/create`` body from the paid order snapshot.

    ``shipping_address`` is the **buyer's** delivery address from the order — Qikink
    dropships straight to them. ``gateway=Prepaid`` because Razorpay already collected
    payment; ``qikink_shipping=1`` lets Qikink run the courier."""
    order = custom.order
    name_parts = (order.ship_full_name or "").split(" ", 1)
    first_name = name_parts[0]
    last_name = name_parts[1] if len(name_parts) > 1 else ""

    return {
        "order_number": custom.idempotency_key,
        "qikink_shipping": "1",
        "gateway": "Prepaid",
        "total_order_value": str(order.total),
        "line_items": [
            {
                "search_from_my_products": 0,
                "quantity": str(custom.quantity),
                "price": str(order.total),
                "sku": custom.variant.sku if custom.variant else "",
                "print_type_id": custom.print_type_id,
                "designs": [
                    {
                        "design_code": custom.idempotency_key,
                        "width_inches": str(custom.width_inches),
                        "height_inches": str(custom.height_inches),
                        "placement_sku": custom.placement_sku,
                        "design_link": design_link(custom),
                        "mockup_link": custom.mockup_file.url if custom.mockup_file else "",
                    }
                ],
            }
        ],
        "shipping_address": {
            "first_name": first_name,
            "last_name": last_name,
            "address1": order.ship_line1,
            "address2": order.ship_line2,
            "phone": order.phone,
            "email": order.email,
            "city": order.ship_city,
            "province": order.ship_state,
            "zip": order.ship_postal_code,
            "country_code": order.ship_country,
        },
    }


def submit_to_qikink(custom: CustomDesignOrder, *, client: QikinkClient | None = None) -> str:
    """Submit a paid custom order to Qikink. Idempotent and gated on review status.

    Returns a short result string. Never raises for the 'already submitted' or 'flagged'
    cases — those are expected no-ops."""
    if custom.qikink_order_id:
        return "already_submitted"
    if not custom.is_submittable:
        logger.info("Custom order %s not submittable (review=%s)", custom.id, custom.review_status)
        return "not_submittable"
    if custom.order is None or not custom.order.is_paid:
        return "not_paid"

    client = client or QikinkClient()
    try:
        resp = client.create_order(build_order_payload(custom))
    except QikinkError:
        custom.submit_status = CustomDesignOrder.SubmitStatus.FAILED
        custom.save(update_fields=["submit_status", "updated_at"])
        raise

    custom.qikink_order_id = str(resp.get("order_id") or resp.get("id") or "")
    custom.qikink_status = "submitted"
    custom.submit_status = CustomDesignOrder.SubmitStatus.SUBMITTED
    custom.submitted_at = timezone.now()
    custom.save(
        update_fields=[
            "qikink_order_id",
            "qikink_status",
            "submit_status",
            "submitted_at",
            "updated_at",
        ]
    )
    # Move the parent order into processing now that the print job is placed.
    _advance_order(custom.order, Order.Status.PROCESSING)
    return "submitted"


def submit_paid_design(custom: CustomDesignOrder) -> str:
    """``submit_to_qikink`` with a Qikink outage downgraded to a logged failure.

    Callers are the payment webhook and the admin retry action, neither of which may be
    rolled back by a third party being unreachable. ``submit_status`` records the
    failure, so the row stays visible for a retry."""
    try:
        return submit_to_qikink(custom)
    except QikinkError as exc:
        logger.warning("Qikink submit failed for %s: %s", custom.id, exc.message)
        return "failed"


def apply_status(
    custom: CustomDesignOrder, qikink_status: str, *, awb: str = "", link: str = ""
) -> None:
    """Record a polled Qikink status and advance the parent order if warranted."""
    custom.qikink_status = qikink_status
    if awb:
        custom.tracking_awb = awb
    if link:
        custom.tracking_link = link if urlsplit(link).scheme.lower() in {"http", "https"} else ""
    if qikink_status in _TERMINAL_QIKINK:
        custom.submit_status = CustomDesignOrder.SubmitStatus.TERMINAL
    custom.save(
        update_fields=[
            "qikink_status",
            "tracking_awb",
            "tracking_link",
            "submit_status",
            "updated_at",
        ]
    )

    target = QIKINK_STATUS_MAP.get(qikink_status)
    if target and custom.order is not None:
        _advance_order(custom.order, target)


def poll_open_orders() -> int:
    """Pull status and tracking for every submitted, non-terminal custom order.

    Qikink publishes no outbound webhook, so polling is the only source of truth for
    status and AWB. One unreachable order never stops the sweep."""
    open_orders = CustomDesignOrder.objects.filter(
        submit_status=CustomDesignOrder.SubmitStatus.SUBMITTED
    ).exclude(qikink_order_id="")
    client = QikinkClient()
    polled = 0
    for custom in open_orders.select_related("order"):
        try:
            data = client.get_order_status(custom.qikink_order_id)
        except QikinkError:
            continue
        status = data.get("status") or data.get("order_status") or ""
        awb = data.get("awb") or data.get("tracking_id") or ""
        link = data.get("tracking_link") or ""
        if status:
            apply_status(custom, status, awb=awb, link=link)
            polled += 1
    return polled


def _advance_order(order: Order, target: str) -> None:
    """Guarded transition: only apply if legal, so out-of-order polls never regress or
    corrupt order state."""
    try:
        order_services.transition(order, target)
    except order_services.OrderError:
        logger.debug("Skipped illegal order transition %s to %s", order.status, target)

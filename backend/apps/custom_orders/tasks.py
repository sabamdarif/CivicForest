"""Celery tasks for custom-order fulfilment.

- ``submit_custom_order_to_qikink`` — enqueued from the verified payment webhook only.
- ``poll_custom_order_statuses`` — Celery Beat periodic job; Qikink has no outbound
  webhook, so we pull status/tracking for all open custom orders (plan.md §8)."""

from __future__ import annotations

import logging

from celery import shared_task

from . import services
from .models import CustomDesignOrder
from .qikink import QikinkClient, QikinkError

logger = logging.getLogger("custom_orders")


@shared_task(bind=True, max_retries=5, default_retry_delay=30)
def submit_custom_order_to_qikink(self, custom_id: str) -> str:
    custom = (
        CustomDesignOrder.objects.select_related("order", "variant").filter(id=custom_id).first()
    )
    if custom is None:
        return "missing"
    try:
        return services.submit_to_qikink(custom)
    except QikinkError as exc:
        if self.request.is_eager:
            # No broker to retry against (tests / eager dev) — surface the failure state.
            logger.warning("Qikink submit failed for %s: %s", custom_id, exc.message)
            return "failed"
        raise self.retry(exc=exc) from exc


@shared_task
def poll_custom_order_statuses() -> int:
    """Poll every non-terminal, submitted custom order and update status/tracking."""
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
            services.apply_status(custom, status, awb=awb, link=link)
            polled += 1
    return polled

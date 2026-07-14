from __future__ import annotations

from django.db import models

from apps.common.models import UUIDTimestampedModel
from apps.orders.models import Order


class Payment(UUIDTimestampedModel):
    """A payment attempt against an order. One Razorpay order id per row; the captured
    payment id + signature are filled once the gateway confirms."""

    class Status(models.TextChoices):
        CREATED = "created", "Created"
        CAPTURED = "captured", "Captured"
        FAILED = "failed", "Failed"

    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="payments")
    gateway = models.CharField(max_length=20, default="razorpay")
    gateway_order_id = models.CharField(max_length=64, unique=True, db_index=True)
    gateway_payment_id = models.CharField(max_length=64, blank=True, db_index=True)
    signature = models.CharField(max_length=128, blank=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default="INR")
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.CREATED)
    verified_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.gateway_order_id} ({self.status})"


class WebhookEvent(UUIDTimestampedModel):
    """De-duplication ledger for provider webhooks. Providers retry deliveries, so we
    record each event id and skip any we've already processed (plan.md §9)."""

    gateway = models.CharField(max_length=20, default="razorpay")
    event_id = models.CharField(max_length=128, db_index=True)
    event_type = models.CharField(max_length=64, blank=True)
    processed = models.BooleanField(default=False)
    # Stored for audit; scrub PII before persisting anything sensitive.
    payload = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["gateway", "event_id"], name="uniq_gateway_event")
        ]

    def __str__(self):
        return f"{self.gateway}:{self.event_id}"

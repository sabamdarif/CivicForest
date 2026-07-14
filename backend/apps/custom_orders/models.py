from __future__ import annotations

import uuid

from django.conf import settings
from django.db import models

from apps.catalog.models import ProductVariant
from apps.common.models import UUIDTimestampedModel
from apps.orders.models import Order


def design_upload_path(instance, filename: str) -> str:
    """Randomised, non-guessable private key — never the original filename, and never a
    path a customer could enumerate (plan.md §8)."""
    return f"designs/{uuid.uuid4().hex}.png"


class CustomDesignOrder(UUIDTimestampedModel):
    """A customer's custom-print request. The uploaded art is content-validated and
    re-encoded before it lands here. Submitted to Qikink only after payment is verified;
    Qikink then dropships it straight to the buyer's address (plan.md §8)."""

    class ReviewStatus(models.TextChoices):
        AUTO_OK = "auto_ok", "Auto-approved"
        FLAGGED = "flagged", "Flagged for review"
        APPROVED = "approved", "Manually approved"
        REJECTED = "rejected", "Rejected"

    class SubmitStatus(models.TextChoices):
        PENDING_PAYMENT = "pending_payment", "Pending payment"
        SUBMITTED = "submitted", "Submitted to Qikink"
        FAILED = "failed", "Submission failed"
        TERMINAL = "terminal", "Terminal (delivered/returned/cancelled)"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="custom_designs"
    )
    order = models.ForeignKey(
        Order, null=True, blank=True, on_delete=models.SET_NULL, related_name="custom_designs"
    )
    variant = models.ForeignKey(
        ProductVariant, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )

    # Re-encoded design art in private object storage; served to Qikink via a signed URL.
    design_file = models.FileField(upload_to=design_upload_path)
    mockup_file = models.FileField(upload_to=design_upload_path, blank=True)

    # Print placement parameters (Qikink line-item fields).
    print_type_id = models.PositiveSmallIntegerField(default=1)
    placement_sku = models.CharField(max_length=8, default="fr", help_text="e.g. fr = front")
    width_inches = models.DecimalField(max_digits=5, decimal_places=2, default=12)
    height_inches = models.DecimalField(max_digits=5, decimal_places=2, default=14)
    quantity = models.PositiveSmallIntegerField(default=1)

    review_status = models.CharField(
        max_length=10, choices=ReviewStatus.choices, default=ReviewStatus.AUTO_OK
    )
    review_reason = models.CharField(max_length=200, blank=True)

    submit_status = models.CharField(
        max_length=16, choices=SubmitStatus.choices, default=SubmitStatus.PENDING_PAYMENT
    )
    # Our order number doubles as the Qikink idempotency key; unique per custom line so a
    # retried submit can never create a duplicate print job at Qikink (plan.md §8).
    idempotency_key = models.CharField(
        max_length=64, unique=True, default=uuid.uuid4, editable=False
    )

    qikink_order_id = models.CharField(max_length=64, blank=True, db_index=True)
    qikink_status = models.CharField(max_length=32, blank=True)
    tracking_awb = models.CharField(max_length=64, blank=True)
    tracking_link = models.URLField(blank=True)
    submitted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"CustomDesign({self.idempotency_key})"

    @property
    def is_submittable(self) -> bool:
        return (
            self.review_status in {self.ReviewStatus.AUTO_OK, self.ReviewStatus.APPROVED}
            and not self.qikink_order_id
        )

    @property
    def is_terminal(self) -> bool:
        return self.submit_status == self.SubmitStatus.TERMINAL

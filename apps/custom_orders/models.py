"""Custom-print domain models.

Three rows model the custom line, and the split matters:

- ``CustomBlank`` is a thin configuration layer over a hidden ``catalog.Product``: the blank
  garments are sold only through ``/customise/`` (``Product.is_custom_blank``), yet ride the
  ordinary variant/cart/order/shipment machinery so none of it is duplicated.
- ``DesignUpload`` is one piece of artwork, uploaded straight to private R2 (never through
  Django) and sanitised out of the request path. It is reusable across orders, so review
  attaches here, once.
- ``CustomDesignOrder`` binds a design to a blank variant with placement and a snapshotted
  print surcharge, and carries the Qikink submission state. Submitted only after payment is
  verified and the design's review has passed; ``idempotency_key`` doubles as the Qikink
  ``order_number`` (<= 15 chars) so a retried submit can never create a second print job
  (rebuild/03-architecture.md §6, §8)."""

from __future__ import annotations

import uuid

from django.conf import settings
from django.db import models

from apps.catalog.models import Product, ProductVariant
from apps.common.models import UUIDTimestampedModel
from apps.orders.models import Order


def generate_design_key() -> str:
    """A Qikink ``order_number`` for one custom line: unique and <= 15 chars (Qikink's hard
    cap, rebuild/02-research.md §3). 14 chars here, uniqueness enforced by the field."""
    return "D" + uuid.uuid4().hex[:13]


class CustomBlank(UUIDTimestampedModel):
    """A blank garment offered in the design tool, mapped one-to-one to a hidden catalog
    product so pricing, stock and fulfilment reuse the catalogue.

    ``print_areas`` is keyed by placement ("front"/"back"); each entry carries the Qikink
    ``placement_sku``, the printable bounds in inches, and the pixel box the preview draws
    the dashed outline from. ``surcharge_tiers`` is a list evaluated smallest-fit-first by
    ``services.surcharge_for``; an empty list means the print carries no surcharge."""

    product = models.OneToOneField(Product, on_delete=models.CASCADE, related_name="custom_blank")
    slug = models.SlugField(max_length=80, unique=True)
    tagline = models.CharField(max_length=160, blank=True)
    print_type_id = models.PositiveSmallIntegerField(default=1)
    print_areas = models.JSONField(default=dict)
    surcharge_tiers = models.JSONField(
        default=list,
        blank=True,
        help_text="[{max_width_in, max_height_in, surcharge}], smallest tier first.",
    )
    display_order = models.PositiveSmallIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["display_order", "slug"]

    def __str__(self):
        return self.slug

    def get_absolute_url(self) -> str:
        return f"/customise/{self.slug}/"


class DesignUpload(UUIDTimestampedModel):
    """One piece of customer artwork in the private designs bucket, reusable across orders.

    The browser PUTs the raw bytes straight to ``r2_key_raw`` with a presigned URL; Django
    never receives them (Vercel's 4.5 MB body cap). The out-of-request sanitise step content-
    sniffs, re-encodes to a clean PNG at ``r2_key_print``, records the real dimensions and a
    coarse DPI estimate, then deletes the raw file. Review attaches here because the artwork
    is what a moderator judges, and passing it once clears every reuse."""

    class Status(models.TextChoices):
        UPLOADING = "uploading", "Awaiting upload"
        UPLOADED = "uploaded", "Uploaded, not yet sanitised"
        READY = "ready", "Sanitised and print-ready"
        FAILED = "failed", "Sanitisation failed"

    class ReviewStatus(models.TextChoices):
        PENDING = "pending", "Pending review"
        AUTO_OK = "auto_ok", "Auto-approved"
        FLAGGED = "flagged", "Flagged for review"
        APPROVED = "approved", "Manually approved"
        REJECTED = "rejected", "Rejected"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="design_uploads",
    )
    r2_key_raw = models.CharField(max_length=200, blank=True)
    r2_key_print = models.CharField(max_length=200, blank=True)
    r2_key_mockup = models.CharField(max_length=200, blank=True)
    declared_mime = models.CharField(max_length=40, blank=True)
    mime = models.CharField(max_length=40, blank=True)
    bytes = models.PositiveIntegerField(default=0)
    width_px = models.PositiveIntegerField(default=0)
    height_px = models.PositiveIntegerField(default=0)
    dpi_estimate = models.PositiveIntegerField(default=0)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.UPLOADING)
    sanitised_at = models.DateTimeField(null=True, blank=True)
    review_status = models.CharField(
        max_length=10, choices=ReviewStatus.choices, default=ReviewStatus.PENDING
    )
    review_reason = models.CharField(max_length=200, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"DesignUpload({self.pk})"

    @property
    def is_reviewed_ok(self) -> bool:
        return self.review_status in {self.ReviewStatus.AUTO_OK, self.ReviewStatus.APPROVED}


class CustomDesignOrder(UUIDTimestampedModel):
    """A design bound to a blank variant: placement, snapshotted surcharge, and Qikink state.

    Reaches Qikink only after payment is verified AND the design's review has passed.
    ``idempotency_key`` doubles as the Qikink ``order_number``, so a retried submit can never
    create a second print job (rebuild/03-architecture.md §6)."""

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
    blank_variant = models.ForeignKey(
        ProductVariant, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )

    design_upload = models.ForeignKey(
        DesignUpload, null=True, blank=True, on_delete=models.PROTECT, related_name="front_orders"
    )
    back_design_upload = models.ForeignKey(
        DesignUpload, null=True, blank=True, on_delete=models.PROTECT, related_name="back_orders"
    )

    # Front placement (Qikink line-item fields).
    print_type_id = models.PositiveSmallIntegerField(default=1)
    placement_sku = models.CharField(max_length=8, default="fr", help_text="e.g. fr = front")
    width_inches = models.DecimalField(max_digits=5, decimal_places=2, default=12)
    height_inches = models.DecimalField(max_digits=5, decimal_places=2, default=14)

    # Optional back placement; a blank placement_sku means no back print.
    back_placement_sku = models.CharField(max_length=8, blank=True)
    back_width_inches = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    back_height_inches = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)

    quantity = models.PositiveSmallIntegerField(default=1)
    # Server-computed at add-to-cart, snapshotted so a later tier change can't rewrite it.
    print_surcharge = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    # The exact rights wording the customer ticked (M7.11), frozen per line.
    rights_ack_text = models.TextField(blank=True)

    submit_status = models.CharField(
        max_length=16, choices=SubmitStatus.choices, default=SubmitStatus.PENDING_PAYMENT
    )
    idempotency_key = models.CharField(
        max_length=15, unique=True, default=generate_design_key, editable=False
    )

    qikink_order_id = models.CharField(max_length=64, blank=True, db_index=True)
    qikink_status = models.CharField(max_length=32, blank=True)
    qikink_last_polled_at = models.DateTimeField(null=True, blank=True)
    tracking_awb = models.CharField(max_length=64, blank=True)
    tracking_link = models.URLField(blank=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    retry_count = models.PositiveSmallIntegerField(default=0)
    last_error = models.CharField(max_length=300, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"CustomDesign({self.idempotency_key})"

    @property
    def is_submittable(self) -> bool:
        """Ready for Qikink: front art reviewed OK, any back art reviewed OK too, and not
        already submitted. Payment and order state are checked by the service layer."""
        if self.design_upload is None or not self.design_upload.is_reviewed_ok:
            return False
        if self.back_design_upload is not None and not self.back_design_upload.is_reviewed_ok:
            return False
        return not self.qikink_order_id

    @property
    def is_terminal(self) -> bool:
        return self.submit_status == self.SubmitStatus.TERMINAL

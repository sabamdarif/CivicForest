import uuid

from django.conf import settings
from django.db import models


class UUIDTimestampedModel(models.Model):
    """Abstract base: UUID primary key + created/updated timestamps.

    UUID pks avoid the enumeration risk of sequential integer ids for anything a
    customer can reference in a URL (plan.md §4).
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True
        ordering = ["-created_at"]


class StockAdjustment(UUIDTimestampedModel):
    """A stock change and why it happened (O6): stock is never edited silently.

    ``resulting_quantity`` snapshots the on-hand count after the change, so the ledger reads
    without replaying every delta. FK targets are strings so this base app never imports catalog
    or accounts. Written only through `apps.catalog.services.adjust_stock`, which applies the
    delta and this row in one transaction.
    """

    class Reason(models.TextChoices):
        RECEIVED = "received", "Stock received"
        DAMAGED = "damaged", "Damaged or lost"
        CORRECTION = "correction", "Count correction"
        RETURN = "return", "Customer return"
        OTHER = "other", "Other"

    variant = models.ForeignKey(
        "catalog.ProductVariant", on_delete=models.CASCADE, related_name="stock_adjustments"
    )
    delta = models.IntegerField(help_text="Positive adds stock, negative removes it.")
    resulting_quantity = models.PositiveIntegerField()
    reason = models.CharField(max_length=20, choices=Reason.choices)
    note = models.TextField(blank=True)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )

    def __str__(self):
        return f"{self.variant_id}: {self.delta:+d} ({self.reason})"

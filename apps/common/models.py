import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone


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


class JobRun(UUIDTimestampedModel):
    """One run of a scheduled job (M8.13): what ran, when, how much it processed and any error.

    A run ledger, not the full `03-architecture.md` §7 engine: no handler registry, per-key
    dedup, backoff or dead-letter, because idempotency already lives in the commands and nothing
    enqueues rows. Written by the cron endpoint and the back-office "run now" button, which both
    call `apps.backoffice.cron.run_named_job`.
    """

    class Status(models.TextChoices):
        RUNNING = "running", "Running"
        DONE = "done", "Done"
        FAILED = "failed", "Failed"

    name = models.CharField(max_length=64)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.RUNNING)
    started_at = models.DateTimeField(default=timezone.now)
    finished_at = models.DateTimeField(null=True, blank=True)
    items_processed = models.PositiveIntegerField(default=0)
    last_error = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["name", "-created_at"])]

    def __str__(self):
        return f"{self.name} ({self.status})"


class OutboundEmail(UUIDTimestampedModel):
    """A ledger row for every transactional email (M8.13): proof of what was sent, and enough to
    resend it. ``template`` and ``context`` name the sender and its ids so a resend re-renders from
    live data rather than a frozen body. Not audited (it is an audit surface itself)."""

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        SENT = "sent", "Sent"
        FAILED = "failed", "Failed"

    to = models.EmailField()
    template = models.CharField(max_length=64)
    subject = models.CharField(max_length=255, blank=True)
    context = models.JSONField(default=dict, blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    provider_id = models.CharField(max_length=120, blank=True)
    error = models.TextField(blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.template} to {self.to} ({self.status})"

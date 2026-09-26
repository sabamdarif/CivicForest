"""Product reviews, written only by verified purchasers.

A review is tied to the ``OrderItem`` it is about (K1), so the buy is proven: the queryset that
mints the write form starts from the customer's own paid order lines, and the model is unique per
order line so one purchase writes one review. Nothing is shown until a moderator publishes it (K4);
the aggregate the product page and JSON-LD read is recomputed by ``services`` on that transition,
never trusted from a client and never counting an unpublished row.
"""

from __future__ import annotations

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from apps.catalog.models import Product
from apps.common.models import UUIDTimestampedModel
from apps.orders.models import OrderItem


class Review(UUIDTimestampedModel):
    class FitFeedback(models.TextChoices):
        SMALL = "runs_small", "Runs small"
        TRUE = "true_to_size", "True to size"
        LARGE = "runs_large", "Runs large"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        PUBLISHED = "published", "Published"
        REJECTED = "rejected", "Rejected"

    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="reviews")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="reviews"
    )
    # The proof of purchase. Unique, so one bought line writes exactly one review; a customer who
    # bought the same product on two orders has two lines and may review each.
    order_item = models.OneToOneField(OrderItem, on_delete=models.CASCADE, related_name="review")
    rating = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    title = models.CharField(max_length=120, blank=True)
    body = models.TextField(blank=True)
    fit_feedback = models.CharField(max_length=16, choices=FitFeedback.choices, blank=True)
    status = models.CharField(
        max_length=12, choices=Status.choices, default=Status.PENDING, db_index=True
    )
    published_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["product", "status"])]

    def __str__(self):
        return f"{self.rating}★ {self.product.name} by {self.user_id}"

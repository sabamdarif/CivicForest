from __future__ import annotations

import secrets

from django.conf import settings
from django.db import models

from apps.catalog.models import ProductVariant
from apps.common.models import UUIDTimestampedModel

# Public order-number alphabet: unambiguous uppercase + digits (no O/0/I/1 confusion).
_ORDER_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"


def generate_order_number() -> str:
    """A short, non-guessable public order reference (e.g. ``CF-7Q3KX9AR``).

    Random rather than sequential so customers can't enumerate ``/orders/2`` to probe
    for other people's orders (plan.md §4)."""
    body = "".join(secrets.choice(_ORDER_ALPHABET) for _ in range(8))
    return f"CF-{body}"


class Order(UUIDTimestampedModel):
    """An immutable purchase record. Totals and the shipping address are **snapshotted**
    at creation from a server-side re-price — never recomputed from live catalog prices
    later (prices change) and never accepted from the client (plan.md §9, §10)."""

    class Status(models.TextChoices):
        CREATED = "created", "Created"
        PAYMENT_PENDING = "payment_pending", "Payment pending"
        PAID = "paid", "Paid"
        PROCESSING = "processing", "Processing"
        SHIPPED = "shipped", "Shipped"
        DELIVERED = "delivered", "Delivered"
        CANCELLED = "cancelled", "Cancelled"
        REFUNDED = "refunded", "Refunded"

    order_number = models.CharField(
        max_length=16, unique=True, default=generate_order_number, editable=False
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="orders"
    )
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PAYMENT_PENDING, db_index=True
    )
    checkout_key = models.CharField(
        max_length=64, blank=True, null=True, unique=True, db_index=True
    )

    # Contact + shipping snapshot (immutable copy taken at checkout).
    email = models.EmailField()
    phone = models.CharField(max_length=20, blank=True)
    ship_full_name = models.CharField(max_length=120)
    ship_line1 = models.CharField(max_length=255)
    ship_line2 = models.CharField(max_length=255, blank=True)
    ship_city = models.CharField(max_length=100)
    ship_state = models.CharField(max_length=100)
    ship_postal_code = models.CharField(max_length=16)
    ship_country = models.CharField(max_length=2, default="IN")

    # Monetary snapshot — copied from cart.services.price_cart at creation.
    currency = models.CharField(max_length=3, default="INR")
    subtotal = models.DecimalField(max_digits=10, decimal_places=2)
    discount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    shipping_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=10, decimal_places=2)
    coupon_code = models.CharField(max_length=40, blank=True)

    has_custom_items = models.BooleanField(default=False)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.order_number

    @property
    def is_paid(self) -> bool:
        return self.status in {
            self.Status.PAID,
            self.Status.PROCESSING,
            self.Status.SHIPPED,
            self.Status.DELIVERED,
        }


class OrderItem(UUIDTimestampedModel):
    """A purchased line, fully snapshotted so the record survives the variant being
    edited or deleted afterwards."""

    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    cart_item_id = models.UUIDField(null=True, blank=True, editable=False)
    variant = models.ForeignKey(
        ProductVariant, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    product_name = models.CharField(max_length=160)
    variant_sku = models.CharField(max_length=64)
    size = models.CharField(max_length=16, blank=True)
    color = models.CharField(max_length=40, blank=True)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    quantity = models.PositiveIntegerField()
    line_total = models.DecimalField(max_digits=10, decimal_places=2)
    is_custom = models.BooleanField(default=False)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.quantity} × {self.product_name} ({self.variant_sku})"

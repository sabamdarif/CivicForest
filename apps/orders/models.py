"""Order records and their fulfilment: the immutable ``Order``/``OrderItem`` snapshot, the
per-dispatch ``Shipment`` (one order can fan out into a stock and a custom shipment), and the
``StatusEvent`` audit trail. Totals and the address are snapshotted at creation and never
recomputed from live catalogue data; order status is derived from shipments, not set by hand."""

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
        PARTIALLY_SHIPPED = "partially_shipped", "Partially shipped"
        SHIPPED = "shipped", "Shipped"
        DELIVERED = "delivered", "Delivered"
        CANCELLED = "cancelled", "Cancelled"
        REFUNDED = "refunded", "Refunded"

    class Fulfilment(models.TextChoices):
        STOCK = "stock", "Stock"
        CUSTOM = "custom", "Custom"
        MIXED = "mixed", "Mixed"

    # The statuses that mean money was taken, as a set a queryset can filter on: the
    # popularity sort counts units sold across exactly these.
    PAID_STATUSES = (
        Status.PAID,
        Status.PROCESSING,
        Status.PARTIALLY_SHIPPED,
        Status.SHIPPED,
        Status.DELIVERED,
    )

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
    fulfilment_kind = models.CharField(
        max_length=8, choices=Fulfilment.choices, default=Fulfilment.STOCK
    )

    # Consent record for "no dark patterns": the exact terms text the customer ticked at
    # checkout, snapshotted so a later wording change can't rewrite what they agreed to.
    rights_ack_text = models.TextField(blank=True)

    cancelled_at = models.DateTimeField(null=True, blank=True)
    cancel_reason = models.CharField(max_length=200, blank=True)

    class Meta:
        ordering = ["-created_at"]
        # Back-office actions that map to no add/change/delete: refund and status change are
        # gated on these so a role (O11) can view orders without moving money or state (M8.2).
        permissions = [
            ("refund_order", "Can refund an order"),
            ("transition_order", "Can change an order's status"),
        ]

    def __str__(self):
        return self.order_number

    @property
    def is_paid(self) -> bool:
        return self.status in set(self.PAID_STATUSES)


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


class Shipment(UUIDTimestampedModel):
    """One physical dispatch. A mixed order fans out into two: the stock shipment CivicForest
    packs, and the custom shipment Qikink prints and dropships, each with its own carrier, AWB
    and dates (architecture §6). Order status is derived from these, never set by hand."""

    class Kind(models.TextChoices):
        STOCK = "stock", "Stock"
        CUSTOM = "custom", "Custom"

    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="shipments")
    kind = models.CharField(max_length=8, choices=Kind.choices)
    items = models.ManyToManyField(OrderItem, related_name="shipments")
    carrier = models.CharField(max_length=60, blank=True)
    awb = models.CharField(max_length=64, blank=True)
    tracking_url = models.URLField(blank=True)
    shipped_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["created_at"]
        constraints = [
            models.UniqueConstraint(fields=["order", "kind"], name="uniq_order_shipment_kind")
        ]

    def __str__(self):
        return f"{self.order.order_number} {self.kind} shipment"


class StatusEvent(UUIDTimestampedModel):
    """One row per status change: the customer's timeline and the staff audit trail in one
    place (architecture §5). Written by ``services.transition``, never edited."""

    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="status_events")
    from_status = models.CharField(max_length=20, blank=True, choices=Order.Status.choices)
    to_status = models.CharField(max_length=20, choices=Order.Status.choices)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    note = models.CharField(max_length=200, blank=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.order.order_number}: {self.from_status}→{self.to_status}"

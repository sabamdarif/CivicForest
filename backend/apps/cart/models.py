from __future__ import annotations

from decimal import Decimal

from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.catalog.models import Product, ProductVariant
from apps.common.models import UUIDTimestampedModel

TWO_PLACES = Decimal("0.01")


class Coupon(UUIDTimestampedModel):
    """A discount code. Validated **only** server-side at pricing/checkout time — the
    client never sends a discount amount, only a code to be verified (plan.md §6, §10)."""

    class DiscountType(models.TextChoices):
        PERCENT = "percent", "Percentage"
        FLAT = "flat", "Flat amount"

    code = models.CharField(max_length=40, unique=True)
    discount_type = models.CharField(max_length=8, choices=DiscountType.choices)
    value = models.DecimalField(max_digits=10, decimal_places=2)
    min_order_value = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0"))
    max_uses = models.PositiveIntegerField(
        null=True, blank=True, help_text="Blank = unlimited redemptions."
    )
    used_count = models.PositiveIntegerField(default=0)
    expires_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["code"]

    def __str__(self):
        return self.code

    def validate_for(self, subtotal: Decimal) -> tuple[bool, str]:
        """Return (is_valid, reason). Reason is a client-safe message when invalid."""
        if not self.is_active:
            return False, "This coupon is no longer active."
        if self.expires_at is not None and self.expires_at < timezone.now():
            return False, "This coupon has expired."
        if self.max_uses is not None and self.used_count >= self.max_uses:
            return False, "This coupon has reached its usage limit."
        if subtotal < self.min_order_value:
            return False, f"Spend at least ₹{self.min_order_value:.0f} to use this coupon."
        return True, ""

    def discount_for(self, subtotal: Decimal) -> Decimal:
        """Discount amount for a given subtotal — never more than the subtotal itself."""
        if self.discount_type == self.DiscountType.PERCENT:
            amount = (subtotal * self.value) / Decimal("100")
        else:
            amount = self.value
        amount = min(amount, subtotal)
        return amount.quantize(TWO_PLACES)


class Cart(UUIDTimestampedModel):
    """A shopping cart, owned by a user or (for guests) keyed to a session.

    Exactly one open cart per owner. A guest cart is merged into the user's cart on
    login (see ``services.merge_guest_cart_into_user``). Totals are never stored — they
    are always recomputed server-side by ``services.price_cart`` so a stale or tampered
    value can never reach checkout (plan.md §10)."""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="cart",
    )
    session_key = models.CharField(max_length=64, blank=True, db_index=True)
    coupon = models.ForeignKey(
        Coupon, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["session_key"],
                condition=models.Q(user__isnull=True) & ~models.Q(session_key=""),
                name="uniq_guest_cart_per_session",
            )
        ]

    def __str__(self):
        owner = self.user.email if self.user_id else f"guest:{self.session_key}"
        return f"Cart({owner})"


class CartItem(UUIDTimestampedModel):
    """A line in a cart. Quantity is re-validated against live stock on every mutation;
    the unit price is always read from the variant, never accepted from the client."""

    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name="items")
    variant = models.ForeignKey(ProductVariant, on_delete=models.CASCADE, related_name="+")
    quantity = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ["created_at"]
        constraints = [
            models.UniqueConstraint(fields=["cart", "variant"], name="uniq_variant_per_cart")
        ]

    def __str__(self):
        return f"{self.quantity} × {self.variant}"


class Wishlist(UUIDTimestampedModel):
    """A saved product per user. Product-level to match the storefront's heart toggle
    on product cards (plan.md §4)."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="wishlist_items"
    )
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="+")

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["user", "product"], name="uniq_wishlist_entry")
        ]

    def __str__(self):
        return f"{self.user.email} ♥ {self.product.name}"

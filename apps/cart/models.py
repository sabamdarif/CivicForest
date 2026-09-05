from __future__ import annotations

from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from apps.catalog.models import Category, Product, ProductVariant
from apps.common.models import UUIDTimestampedModel

TWO_PLACES = Decimal("0.01")


class Coupon(UUIDTimestampedModel):
    """A discount code. Validated **only** server-side at pricing/checkout time — the
    client never sends a discount amount, only a code to be verified (plan.md §6, §10).

    The rules live in ``services.check_coupon`` rather than here: two of them read the
    customer's order history and their redemptions, and a model that reaches into another
    app's tables is the thing this codebase keeps out of models."""

    class DiscountType(models.TextChoices):
        PERCENT = "percent", "Percentage"
        FLAT = "flat", "Flat amount"

    code = models.CharField(max_length=40, unique=True)
    discount_type = models.CharField(max_length=8, choices=DiscountType.choices)
    value = models.DecimalField(max_digits=10, decimal_places=2)
    free_shipping = models.BooleanField(
        default=False, help_text="Waives the shipping fee on top of any amount off (J1)."
    )
    min_order_value = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0"))
    max_uses = models.PositiveIntegerField(
        null=True, blank=True, help_text="Blank = unlimited redemptions."
    )
    per_user_limit = models.PositiveIntegerField(
        null=True, blank=True, help_text="Blank = unlimited per customer."
    )
    used_count = models.PositiveIntegerField(default=0)
    starts_at = models.DateTimeField(null=True, blank=True, help_text="Blank = live now.")
    expires_at = models.DateTimeField(null=True, blank=True)
    first_order_only = models.BooleanField(
        default=False, help_text="Only for a customer with no paid order yet."
    )
    exclude_sale_items = models.BooleanField(
        default=False, help_text="Skip lines already discounted against their MRP."
    )
    # Blank scope means the whole catalogue. A line qualifies if it matches either list.
    scope_categories = models.ManyToManyField(Category, blank=True, related_name="+")
    scope_products = models.ManyToManyField(Product, blank=True, related_name="+")
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["code"]

    def __str__(self):
        return self.code

    def clean(self):
        """A coupon that takes nothing off and waives nothing is a support call waiting to
        happen, so the admin form refuses it."""
        if not self.value and not self.free_shipping:
            raise ValidationError(
                {"value": "Enter an amount off, or tick free shipping, or the coupon does nothing."}
            )

    def discount_for(self, subtotal: Decimal) -> Decimal:
        """Discount amount for a given subtotal, never more than the subtotal itself.

        The caller passes the total of the lines this coupon actually covers, which is not
        the cart subtotal once a scope or a sale exclusion is in play."""
        if self.discount_type == self.DiscountType.PERCENT:
            amount = (subtotal * self.value) / Decimal("100")
        else:
            amount = self.value
        amount = min(amount, subtotal)
        return amount.quantize(TWO_PLACES)


class CouponRedemption(UUIDTimestampedModel):
    """One paid order's use of a coupon, which is the only thing that counts as a use (J2).

    An applied coupon deliberately writes no row: otherwise a customer exhausts a code by
    applying it and walking away, and a public code's uses could be burned by anyone. Unique
    on coupon and order, so a replayed payment webhook cannot count twice."""

    coupon = models.ForeignKey(Coupon, on_delete=models.CASCADE, related_name="redemptions")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="coupon_redemptions"
    )
    order = models.ForeignKey(
        "orders.Order", on_delete=models.CASCADE, related_name="coupon_redemptions"
    )

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["coupon", "order"], name="uniq_coupon_per_order")
        ]

    def __str__(self):
        return f"{self.coupon.code} by {self.user.email}"


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
    reminded_at = models.DateTimeField(
        null=True, blank=True, help_text="When the abandoned-cart reminder went out (G5)."
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

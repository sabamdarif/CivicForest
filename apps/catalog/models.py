from decimal import Decimal

from django.db import models
from django.utils.text import slugify

from apps.common.models import UUIDTimestampedModel


class Material(UUIDTimestampedModel):
    """Admin-configurable fabric/material (e.g. Cotton, Fleece) — a table, not a
    hardcoded choice, so it stays editable (plan.md §4)."""

    name = models.CharField(max_length=80, unique=True)
    slug = models.SlugField(max_length=90, unique=True, blank=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)


class Size(UUIDTimestampedModel):
    """Admin-configurable size option (S, M, 32, …).

    Variants keep storing the label itself, so orders/cart/search are untouched; this
    table is the controlled vocabulary the admin form offers and the shop facets sort
    by, which is what stops "M" and "m" becoming two filter entries.
    """

    name = models.CharField(max_length=16, unique=True)
    display_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["display_order", "name"]

    def __str__(self):
        return self.name


class Color(UUIDTimestampedModel):
    """Admin-configurable color option with its swatch. Same vocabulary role as
    :class:`Size`; ``hex`` pre-fills ``ProductVariant.color_hex``."""

    name = models.CharField(max_length=40, unique=True)
    hex = models.CharField(max_length=7, blank=True, help_text="#RRGGBB swatch")
    display_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["display_order", "name"]

    def __str__(self):
        return self.name


class Category(UUIDTimestampedModel):
    """Product category. ``parent`` is nullable so subcategories can be added later
    without a schema change."""

    name = models.CharField(max_length=80)
    slug = models.SlugField(max_length=90, unique=True)
    parent = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="children",
    )
    description = models.CharField(max_length=255, blank=True)
    display_order = models.PositiveSmallIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["display_order", "name"]
        verbose_name_plural = "categories"

    def __str__(self):
        return self.name


class Tag(UUIDTimestampedModel):
    name = models.CharField(max_length=60, unique=True)
    slug = models.SlugField(max_length=70, unique=True, blank=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)


class Product(UUIDTimestampedModel):
    """A sellable product. Price/flags are server-owned and never client-writable."""

    name = models.CharField(max_length=160)
    slug = models.SlugField(max_length=180, unique=True)
    description = models.TextField(blank=True)
    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name="products")
    material = models.ForeignKey(
        Material, null=True, blank=True, on_delete=models.SET_NULL, related_name="products"
    )
    tags = models.ManyToManyField(Tag, blank=True, related_name="products")
    base_price = models.DecimalField(max_digits=10, decimal_places=2)

    is_new = models.BooleanField(default=False)
    is_bestseller = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    # SEO fields rendered server-side by Next.js.
    meta_title = models.CharField(max_length=180, blank=True)
    meta_description = models.CharField(max_length=300, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["is_active", "is_new"]),
            models.Index(fields=["is_active", "is_bestseller"]),
        ]

    def __str__(self):
        return self.name

    @property
    def price_from(self) -> Decimal:
        """Lowest sellable price across active variants, falling back to base."""
        prices = [v.effective_price for v in self.variants.all() if v.is_active]
        return min(prices) if prices else self.base_price

    @property
    def in_stock(self) -> bool:
        return any(v.is_active and v.stock_quantity > 0 for v in self.variants.all())


class ProductVariant(UUIDTimestampedModel):
    """A concrete purchasable SKU: size + color, with its own stock and optional
    price override. Filters (size/color/price) and stock map onto this (plan.md §4)."""

    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="variants")
    size = models.CharField(max_length=16)
    color = models.CharField(max_length=40)
    color_hex = models.CharField(max_length=7, blank=True, help_text="#RRGGBB swatch")
    sku = models.CharField(
        max_length=64, unique=True, blank=True, help_text="Auto-generated when left blank."
    )
    price_override = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    stock_quantity = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["size", "color"]
        constraints = [
            models.UniqueConstraint(
                fields=["product", "size", "color"], name="uniq_variant_per_product"
            )
        ]

    def __str__(self):
        return f"{self.product.name} — {self.size}/{self.color}"

    def save(self, *args, **kwargs):
        if not self.sku:
            self.sku = self._generate_sku()
        super().save(*args, **kwargs)

    def _generate_sku(self) -> str:
        """``CLASSIC-BLACK-TEE-M-BLACK``, de-duplicated with a numeric suffix.

        Staff adding a product shouldn't have to invent unique codes by hand; a typed
        SKU still wins because this only runs when the field is blank."""
        stem = slugify(f"{self.product.slug} {self.size} {self.color}").upper()[:58] or "SKU"
        candidate, suffix = stem, 2
        taken = ProductVariant.objects.exclude(pk=self.pk)
        while taken.filter(sku=candidate).exists():
            candidate = f"{stem[:58]}-{suffix}"
            suffix += 1
        return candidate

    @property
    def effective_price(self) -> Decimal:
        """Override if set, else the product base price."""
        return self.price_override if self.price_override is not None else self.product.base_price


class ProductImage(UUIDTimestampedModel):
    """Image at product level (variant optional for color-specific shots)."""

    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="images")
    variant = models.ForeignKey(
        ProductVariant,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="images",
    )
    image = models.ImageField(upload_to="products/")
    alt_text = models.CharField(max_length=160, blank=True)
    display_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["display_order", "created_at"]

    def __str__(self):
        return self.alt_text or f"Image for {self.product.name}"

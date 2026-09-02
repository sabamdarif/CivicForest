"""Catalogue data: the vocabularies, categories, collections, products and their variants.

Two invariants worth knowing before editing: a product carries the legally required
country of origin, HSN code and tax rate and cannot go live without them (C10, L9), and
the discount is never stored, only derived from `mrp` against the selling price (C2).
"""

from decimal import Decimal

from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.db import models
from django.utils.text import slugify

from apps.common.models import UUIDTimestampedModel

# A swatch renders its colour into a style attribute, so an unvalidated hex from the admin
# would be a CSS injection on every page that lists the product.
HEX_COLOUR = RegexValidator(
    r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$", "Use a hex colour like #1f3d2b."
)
HSN_CODE = RegexValidator(r"^\d{4,8}$", "An HSN code is 4 to 8 digits.")


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
    hex = models.CharField(
        max_length=7, blank=True, validators=[HEX_COLOUR], help_text="#RRGGBB swatch"
    )
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
    image = models.ImageField(
        upload_to="categories/", blank=True, help_text="Shop-by-category tile"
    )
    display_order = models.PositiveSmallIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["display_order", "name"]
        verbose_name_plural = "categories"

    def __str__(self):
        return self.name

    # Paths are literal from the URL map in rebuild/03-architecture.md §4, which is the
    # contract the templates and the chrome already link against.
    def get_absolute_url(self) -> str:
        return f"/shop/{self.slug}/"


class Collection(UUIDTimestampedModel):
    """A curated group with its own copy and imagery (C7).

    Not a category: a product belongs to exactly one category and to any number of
    collections.
    """

    name = models.CharField(max_length=120)
    slug = models.SlugField(max_length=140, unique=True)
    tagline = models.CharField(max_length=160, blank=True)
    description = models.TextField(blank=True)
    hero_image = models.ImageField(upload_to="collections/", blank=True)
    display_order = models.PositiveSmallIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["display_order", "name"]

    def __str__(self):
        return self.name

    def get_absolute_url(self) -> str:
        return f"/collections/{self.slug}/"


class SizeChart(UUIDTimestampedModel):
    """One measurement table per garment type (C11), shown in the size-guide accordion.

    ``rows`` holds the header row first, so adding a measurement column needs no migration.
    """

    category = models.OneToOneField(Category, on_delete=models.CASCADE, related_name="size_chart")
    rows = models.JSONField(
        default=list,
        help_text='Header row first: [["Size", "Chest", "Length"], ["S", "38", "27"]]',
    )
    unit = models.CharField(
        max_length=2, choices=[("cm", "centimetres"), ("in", "inches")], default="cm"
    )
    notes = models.CharField(max_length=255, blank=True)

    def __str__(self):
        return f"Size chart for {self.category.name}"


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
    collections = models.ManyToManyField(Collection, blank=True, related_name="products")
    base_price = models.DecimalField(max_digits=10, decimal_places=2)
    mrp = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Printed price. Leave blank when the product is not discounted.",
    )

    # ── Legally required (C10, L9): clean() blocks going live without them ──
    country_of_origin = models.CharField(max_length=60, default="India")
    hsn_code = models.CharField(max_length=8, blank=True, validators=[HSN_CODE])
    tax_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("5.00"),
        help_text="GST percent. Prices are shown tax-inclusive (C3): confirm the current "
        "apparel slab with your CA before launch.",
    )

    # ── Detail the product page and the courier need (C10) ──
    care_instructions = models.TextField(blank=True)
    fit_notes = models.CharField(max_length=255, blank=True)
    model_note = models.CharField(
        max_length=160, blank=True, help_text='e.g. "Model is 6\'1" and wears M"'
    )
    gsm = models.PositiveSmallIntegerField(null=True, blank=True, verbose_name="GSM")
    weight_grams = models.PositiveIntegerField(null=True, blank=True)
    length_cm = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    width_cm = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    height_cm = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)

    is_new = models.BooleanField(
        default=False, help_text="Forces the New badge past its automatic window (C9)."
    )
    is_bestseller = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    # Overrides the defaults the product page derives from the name and description.
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

    def get_absolute_url(self) -> str:
        return f"/product/{self.slug}/"

    def clean(self):
        """A product cannot go live without its HSN code (C10, L9).

        ``hsn_code`` stays blank-able so staff can save a draft before looking the code up,
        and so the migration stays backward compatible on a table that already holds rows.
        Country of origin needs no gate here: it has a default and the form requires it.
        """
        if self.is_active and not self.hsn_code:
            raise ValidationError({"hsn_code": "Required before a product can go live."})

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
    color_hex = models.CharField(
        max_length=7, blank=True, validators=[HEX_COLOUR], help_text="#RRGGBB swatch"
    )
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
    """Image at product level (variant optional for colour-specific shots).

    ``image`` holds the storage key: which bucket or disk it resolves against is
    ``STORAGES["default"]``, so moving the catalogue onto R2 is a settings change and never
    a migration. ``width_variants`` records the derivatives that exist, because an original
    narrower than 1600px has fewer of them and srcset must not promise a file it lacks.
    """

    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="images")
    variant = models.ForeignKey(
        ProductVariant,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="images",
    )
    image = models.ImageField(upload_to="products/")
    width_variants = models.JSONField(default=dict, blank=True, editable=False)
    alt_text = models.CharField(max_length=160, blank=True)
    display_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["display_order", "created_at"]

    def __str__(self):
        return self.alt_text or f"Image for {self.product.name}"

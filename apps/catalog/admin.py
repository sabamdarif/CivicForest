from django import forms
from django.contrib import admin
from django.db.models import Count
from django.utils.html import format_html
from django.utils.safestring import mark_safe

from apps.custom_orders.uploads import UploadError, validate_product_image

from .models import Category, Color, Material, Product, ProductImage, ProductVariant, Size, Tag

EMPTY_THUMB = mark_safe(  # noqa: S308 — constant markup, no user input
    '<span style="display:inline-block;height:44px;width:44px;border-radius:6px;'
    'background:rgba(0,0,0,.06)"></span>'
)
NO_VARIANTS = mark_safe('<span style="color:#b3261e">none — not buyable</span>')
EMPTY_SWATCH = mark_safe(  # noqa: S308 — constant markup, no user input
    '<span style="display:inline-block;height:20px;width:20px;border-radius:4px;'
    'background:rgba(0,0,0,.06)"></span>'
)


def _vocab_choices(model, current: str = "") -> list[tuple[str, str]]:
    """Dropdown options from an admin-managed vocabulary table.

    ``current`` is always included so opening an older variant whose value was retired
    from the table can never silently rewrite it on save.
    """
    names = list(model.objects.values_list("name", flat=True))
    if current and current not in names:
        names.insert(0, current)
    return [("", "---------")] + [(name, name) for name in names]


class MultiFileInput(forms.FileInput):
    allow_multiple_selected = True


class ProductVariantForm(forms.ModelForm):
    """Size/color come from the Size and Color tables instead of free text — the one
    change that stops "Black" and "black" showing up as two shop filters."""

    class Meta:
        model = ProductVariant
        # ``product`` is dropped automatically when this form is used as an inline.
        fields = [
            "product",
            "size",
            "color",
            "color_hex",
            "sku",
            "price_override",
            "stock_quantity",
            "is_active",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["size"].widget = forms.Select(
            choices=_vocab_choices(Size, self.instance.size or "")
        )
        self.fields["color"].widget = forms.Select(
            choices=_vocab_choices(Color, self.instance.color or "")
        )
        self.fields["sku"].required = False
        self.fields["color_hex"].help_text = "Blank = taken from the Color option."

    def clean(self):
        data = super().clean()
        if data.get("color") and not data.get("color_hex"):
            swatch = Color.objects.filter(name=data["color"]).values_list("hex", flat=True).first()
            data["color_hex"] = swatch or ""
        return data


class ProductVariantInline(admin.TabularInline):
    model = ProductVariant
    form = ProductVariantForm
    extra = 2
    verbose_name_plural = "Variants — one row per size/colour you actually sell"


class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 0
    fields = ["preview", "image", "alt_text", "display_order", "variant"]
    readonly_fields = ["preview"]
    verbose_name_plural = "Gallery (drag order via the number column)"

    @admin.display(description="")
    def preview(self, obj):
        if not obj.pk or not obj.image:
            return "—"
        return format_html(
            '<img src="{}" style="height:64px;width:64px;object-fit:cover;'
            'border-radius:6px;border:1px solid rgba(0,0,0,.15)">',
            obj.image.url,
        )


class ProductAdminForm(forms.ModelForm):
    gallery = forms.Field(
        required=False,
        widget=MultiFileInput(
            attrs={"multiple": True, "accept": "image/png,image/jpeg,image/webp"}
        ),
        label="Upload photos",
        help_text="Pick one or many at once — they are appended to the gallery below.",
    )

    class Meta:
        model = Product
        # Every editable field; ``fieldsets`` below decides what staff actually see.
        fields = [
            "name",
            "slug",
            "category",
            "base_price",
            "description",
            "material",
            "tags",
            "is_active",
            "is_new",
            "is_bestseller",
            "meta_title",
            "meta_description",
        ]

    def clean_gallery(self):
        # Same content-sniff/verify gate the customer design upload uses; the field
        # value itself is unused (ProductAdmin reads request.FILES on save).
        for uploaded in self.files.getlist("gallery"):
            try:
                validate_product_image(uploaded)
            except UploadError as exc:
                raise forms.ValidationError(f"{uploaded.name}: {exc.message}") from exc
        return None


@admin.register(Size)
class SizeAdmin(admin.ModelAdmin):
    list_display = ["name", "display_order", "variant_count"]
    list_editable = ["display_order"]
    search_fields = ["name"]
    ordering = ["display_order", "name"]

    @admin.display(description="used by")
    def variant_count(self, obj):
        return ProductVariant.objects.filter(size=obj.name).count()


@admin.register(Color)
class ColorAdmin(admin.ModelAdmin):
    list_display = ["swatch", "name", "hex", "display_order", "variant_count"]
    list_editable = ["display_order"]
    search_fields = ["name"]
    ordering = ["display_order", "name"]

    @admin.display(description="")
    def swatch(self, obj):
        if not obj.hex:
            return EMPTY_SWATCH
        return format_html(
            '<span style="display:inline-block;height:20px;width:20px;border-radius:4px;'
            'background:{};border:1px solid rgba(0,0,0,.2)"></span>',
            obj.hex,
        )

    @admin.display(description="used by")
    def variant_count(self, obj):
        return ProductVariant.objects.filter(color=obj.name).count()


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ["name", "slug", "parent", "display_order", "product_count", "is_active"]
    list_editable = ["display_order", "is_active"]
    list_filter = ["is_active"]
    prepopulated_fields = {"slug": ["name"]}
    search_fields = ["name"]

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(_products=Count("products"))

    @admin.display(description="products", ordering="_products")
    def product_count(self, obj):
        return obj._products


@admin.register(Material)
class MaterialAdmin(admin.ModelAdmin):
    list_display = ["name", "slug"]
    prepopulated_fields = {"slug": ["name"]}
    search_fields = ["name"]


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ["name", "slug"]
    prepopulated_fields = {"slug": ["name"]}
    search_fields = ["name"]


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    form = ProductAdminForm
    list_display = [
        "thumb",
        "name",
        "category",
        "base_price",
        "variant_summary",
        "stock",
        "is_new",
        "is_bestseller",
        "is_active",
    ]
    list_display_links = ["thumb", "name"]
    list_editable = ["is_new", "is_bestseller", "is_active"]
    list_filter = ["category", "material", "is_active", "is_new", "is_bestseller"]
    search_fields = ["name", "slug", "description"]
    prepopulated_fields = {"slug": ["name"]}
    autocomplete_fields = ["category", "material", "tags"]
    inlines = [ProductVariantInline, ProductImageInline]
    save_on_top = True
    fieldsets = [
        (
            None,
            {
                "fields": ["name", "slug", "category", "base_price", "description"],
                "description": "Name, category and price are all a new product needs — "
                "add sizes/colours in Variants below, then drop the photos in.",
            },
        ),
        ("Photos", {"fields": ["gallery"]}),
        ("Details", {"fields": ["material", "tags"]}),
        ("Storefront placement", {"fields": ["is_active", "is_new", "is_bestseller"]}),
        (
            "SEO",
            {"classes": ["collapse"], "fields": ["meta_title", "meta_description"]},
        ),
    ]

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .select_related("category")
            .prefetch_related("images", "variants")
        )

    @admin.display(description="")
    def thumb(self, obj):
        image = next(iter(obj.images.all()), None)
        if not image:
            return format_html(
                '<span style="display:inline-block;height:44px;width:44px;border-radius:6px;'
                'background:rgba(0,0,0,.06)"></span>'
            )
        return format_html(
            '<img src="{}" style="height:44px;width:44px;object-fit:cover;border-radius:6px">',
            image.image.url,
        )

    @admin.display(description="variants")
    def variant_summary(self, obj):
        variants = [v for v in obj.variants.all() if v.is_active]
        if not variants:
            return format_html('<span style="color:#b3261e">none — not buyable</span>')
        return f"{len(variants)} · {len({v.size for v in variants})} sizes"

    @admin.display(description="stock")
    def stock(self, obj):
        total = sum(v.stock_quantity for v in obj.variants.all() if v.is_active)
        color = "#b3261e" if total == 0 else "#146c2e" if total > 5 else "#8a6100"
        return format_html('<b style="color:{}">{}</b>', color, total)

    def save_related(self, request, form, formsets, change):
        """Turn the multi-file picker into ProductImage rows, appended after any
        gallery rows the inline created."""
        super().save_related(request, form, formsets, change)
        uploads = request.FILES.getlist("gallery")
        if not uploads:
            return
        product = form.instance
        start = product.images.count()
        ProductImage.objects.bulk_create(
            [
                ProductImage(
                    product=product,
                    image=upload,
                    alt_text=product.name,
                    display_order=start + offset,
                )
                for offset, upload in enumerate(uploads)
            ]
        )


@admin.register(ProductVariant)
class ProductVariantAdmin(admin.ModelAdmin):
    form = ProductVariantForm
    list_display = ["sku", "product", "size", "color", "stock_quantity", "is_active"]
    list_editable = ["stock_quantity", "is_active"]
    list_filter = ["size", "color", "is_active"]
    search_fields = ["sku", "product__name"]
    raw_id_fields = ["product"]

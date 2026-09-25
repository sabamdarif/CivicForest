"""Back-office catalogue forms: the product form, the variant matrix and the image reorder set.

Server-rendered so product management posts and re-renders without JavaScript, matching the
`orders/forms.py` checkout convention. The variant matrix and image list are Django inline
formsets, the standard tool for editing a product's related rows on one page. Gallery uploads
reuse the customer upload sniffer (`validate_product_image`), so a staff upload is held to the
same content check as a design file.
"""

from __future__ import annotations

from django import forms
from django.forms import inlineformset_factory
from django.utils.text import slugify

from apps.custom_orders.uploads import UploadError, validate_product_image

from .models import Color, Product, ProductImage, ProductVariant, Size


def vocab_choices(model, current: str = "") -> list[tuple[str, str]]:
    """Dropdown options from an admin-managed vocabulary table (Size/Color).

    ``current`` is always kept so editing an older variant whose value was retired from the
    table never silently rewrites it on save.
    """
    names = list(model.objects.values_list("name", flat=True))
    if current and current not in names:
        names.insert(0, current)
    return [("", "---------")] + [(name, name) for name in names]


def unique_product_slug(base: str, exclude_pk=None) -> str:
    """A slug from ``base`` that no other product holds, de-duped with a numeric suffix."""
    stem = slugify(base)[:180] or "product"
    slug, suffix = stem, 2
    taken = Product.objects.exclude(pk=exclude_pk) if exclude_pk else Product.objects.all()
    while taken.filter(slug=slug).exists():
        slug = f"{stem[:176]}-{suffix}"
        suffix += 1
    return slug


class MultiFileInput(forms.FileInput):
    allow_multiple_selected = True


class ProductForm(forms.ModelForm):
    """The full product form. ``slug`` is optional and derived from the name when blank, so a
    staff member never has to invent one; ``gallery`` appends photos, validated on upload."""

    gallery = forms.Field(
        required=False,
        widget=MultiFileInput(
            attrs={"multiple": True, "accept": "image/png,image/jpeg,image/webp"}
        ),
        label="Add photos",
        help_text="Pick one or many; they are appended to the gallery below.",
    )

    class Meta:
        model = Product
        fields = [
            "name",
            "slug",
            "category",
            "base_price",
            "mrp",
            "description",
            "material",
            "tags",
            "collections",
            "country_of_origin",
            "care_instructions",
            "fit_notes",
            "model_note",
            "gsm",
            "weight_grams",
            "length_cm",
            "width_cm",
            "height_cm",
            "is_active",
            "is_new",
            "is_bestseller",
            "meta_title",
            "meta_description",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["slug"].required = False
        self.fields["slug"].help_text = "Leave blank to build it from the name."

    def clean_slug(self):
        slug = (self.cleaned_data.get("slug") or "").strip()
        if slug:
            return slug
        name = self.cleaned_data.get("name") or self.data.get("name") or ""
        return unique_product_slug(name, exclude_pk=self.instance.pk)

    def clean_gallery(self):
        # The field value itself is unused: the view reads request.FILES on save. This only
        # runs the same content sniff the customer upload path uses, so a disguised file is
        # rejected before it becomes a ProductImage.
        for uploaded in self.files.getlist("gallery"):
            try:
                validate_product_image(uploaded)
            except UploadError as exc:
                raise forms.ValidationError(f"{uploaded.name}: {exc.message}") from exc
        return None


class VariantMatrixForm(forms.ModelForm):
    """One row of the variant matrix. Size and colour come from the vocabulary tables, the swatch
    fills itself in from the chosen colour, and a blank SKU auto-generates on save."""

    class Meta:
        model = ProductVariant
        fields = [
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
            choices=vocab_choices(Size, self.instance.size or "")
        )
        self.fields["color"].widget = forms.Select(
            choices=vocab_choices(Color, self.instance.color or "")
        )
        self.fields["sku"].required = False

    def clean(self):
        data = super().clean()
        if data.get("color") and not data.get("color_hex"):
            swatch = Color.objects.filter(name=data["color"]).values_list("hex", flat=True).first()
            data["color_hex"] = swatch or ""
        return data


VariantFormSet = inlineformset_factory(
    Product, ProductVariant, form=VariantMatrixForm, extra=1, can_delete=True
)

ImageFormSet = inlineformset_factory(
    Product,
    ProductImage,
    fields=["display_order", "alt_text", "variant"],
    extra=0,
    can_delete=True,
)

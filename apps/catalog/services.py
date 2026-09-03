"""Catalog read services.

All catalog querysets funnel through here so the same active-only, prefetch-optimized
logic is reused by every view and admin action: the "fat services, thin views" rule
from plan.md §3.
"""

import io
from pathlib import PurePosixPath

from django.core.files.base import ContentFile
from django.db.models import F, Min, Prefetch, Q, QuerySet
from django.db.models.functions import Coalesce
from PIL import Image as PILImage
from PIL import ImageOps

from .models import Category, Material, Product, ProductImage, ProductVariant, Size

# P8 wants three widths. WebP only: it has been universal since 2020, so an AVIF and a JPEG
# alongside it would triple the storage and the upload time for nothing.
IMAGE_WIDTHS = (400, 800, 1600)


def active_products() -> QuerySet[Product]:
    """Base queryset of visible products with related data prefetched.

    Only active variants are prefetched so ``price_from`` / ``in_stock`` reflect what
    a customer can actually buy.
    """
    active_variants = ProductVariant.objects.filter(is_active=True)
    return (
        Product.objects.filter(is_active=True)
        .select_related("category", "material")
        .prefetch_related(
            "images",
            "tags",
            Prefetch("variants", queryset=active_variants),
        )
    )


def product_by_slug(slug: str) -> Product | None:
    return active_products().filter(slug=slug).first()


def with_price(queryset: QuerySet[Product]) -> QuerySet[Product]:
    """Annotate ``price`` = the same number the storefront shows (``price_from``):
    the cheapest active variant's effective price, falling back to base price.

    Price filtering and price sorting both run off this, so "under ₹750" can never
    exclude a product whose card reads ₹749 because its *base* price is higher.
    """
    return queryset.annotate(
        price=Coalesce(
            Min(
                Coalesce("variants__price_override", "base_price"),
                filter=Q(variants__is_active=True),
            ),
            F("base_price"),
        )
    )


def active_categories() -> QuerySet[Category]:
    return Category.objects.filter(is_active=True)


def catalog_facets() -> dict:
    """Filter options that actually return results.

    Derived from live active variants rather than a hardcoded list, so the shop panel
    can never offer a filter that matches nothing. ``Size`` supplies ordering;
    a value with no option row still shows up (it just sorts last).
    """
    variants = ProductVariant.objects.filter(is_active=True, product__is_active=True)
    sizes = variants.order_by().values_list("size", flat=True).distinct()

    size_names = {s.strip() for s in sizes if s.strip()}
    size_order = dict(Size.objects.values_list("name", "display_order"))

    return {
        "categories": [
            {"name": c.name, "slug": c.slug}
            for c in active_categories().order_by("display_order", "name")
        ],
        "sizes": sorted(size_names, key=lambda n: (size_order.get(n, 9999), n)),
        "materials": [
            {"name": m.name, "slug": m.slug}
            for m in Material.objects.filter(products__is_active=True).distinct()
        ],
    }


def new_arrivals(limit: int = 8) -> QuerySet[Product]:
    return active_products().filter(is_new=True)[:limit]


def bestsellers(limit: int = 8) -> QuerySet[Product]:
    return active_products().filter(is_bestseller=True)[:limit]


def build_image_widths(image: ProductImage) -> dict[str, str]:
    """Write the WebP derivatives beside the original and record their storage keys.

    Inline rather than deferred: §7's job system is not built, and a staff member adding a
    handful of photos is not a request worth queueing. Never upscales, so a 900px original
    yields 400 and 800 only and srcset can never promise a file that does not exist.
    """
    field = image.image
    if not field:
        return {}

    with field.open("rb") as handle:
        original = ImageOps.exif_transpose(PILImage.open(handle)).convert("RGB")
    stem = PurePosixPath(field.name).with_suffix("")
    targets = [width for width in IMAGE_WIDTHS if width <= original.width] or [original.width]

    keys: dict[str, str] = {}
    for target in targets:
        derivative = original.copy()
        derivative.thumbnail((target, original.height), PILImage.LANCZOS)
        buffer = io.BytesIO()
        derivative.save(buffer, format="WEBP", quality=82, method=6)
        # Deterministic key, deleted first: re-running converges instead of piling up
        # storage-suffixed duplicates.
        key = f"{stem}.{target}.webp"
        if field.storage.exists(key):
            field.storage.delete(key)
        keys[str(target)] = field.storage.save(key, ContentFile(buffer.getvalue()))

    image.width_variants = keys
    image.save(update_fields=["width_variants", "updated_at"])
    return keys


def srcset(image: ProductImage) -> str:
    """``url 400w, url 800w`` from the recorded derivatives, empty when there are none."""
    if not image.width_variants:
        return ""
    storage = image.image.storage
    return ", ".join(
        f"{storage.url(key)} {width}w"
        for width, key in sorted(image.width_variants.items(), key=lambda pair: int(pair[0]))
    )

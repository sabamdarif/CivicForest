"""Catalog read services.

All catalog querysets funnel through here so the same active-only, prefetch-optimized
logic is reused by every view and admin action: the "fat services, thin views" rule
from plan.md §3.
"""

from django.db.models import F, Min, Prefetch, Q, QuerySet
from django.db.models.functions import Coalesce

from .models import Category, Material, Product, ProductVariant, Size


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

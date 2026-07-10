"""Catalog read services.

All catalog querysets funnel through here so the same active-only, prefetch-optimized
logic is reused by API views, the search reindex job, and any admin action — the
"fat services, thin views" rule from plan.md §3.
"""

from django.db.models import Prefetch, QuerySet

from .models import Category, Product, ProductVariant


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


def active_categories() -> QuerySet[Category]:
    return Category.objects.filter(is_active=True)


def new_arrivals(limit: int = 8) -> QuerySet[Product]:
    return active_products().filter(is_new=True)[:limit]


def bestsellers(limit: int = 8) -> QuerySet[Product]:
    return active_products().filter(is_bestseller=True)[:limit]

"""Denormalized product → search-document mapping.

Everything the suggestion/results UI needs is baked into the document so a query never
joins back to Postgres mid-request (plan.md §7).
"""

from __future__ import annotations

from apps.catalog.models import Product


def product_to_document(product: Product) -> dict:
    variants = [v for v in product.variants.all() if v.is_active]
    images = list(product.images.all())
    thumbnail = images[0].image.url if images else None
    return {
        "id": str(product.id),
        "name": product.name,
        "slug": product.slug,
        "description": product.description,
        "category": product.category.name,
        "category_slug": product.category.slug,
        "tags": [t.name for t in product.tags.all()],
        "sizes": sorted({v.size for v in variants}),
        "colors": sorted({v.color for v in variants}),
        "price_from": float(product.price_from),
        "thumbnail": thumbnail,
        "is_new": product.is_new,
        "is_bestseller": product.is_bestseller,
        "created_at": product.created_at.timestamp(),
    }

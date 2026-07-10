"""Search read services with graceful Postgres fallback.

The suggestion/results endpoints call ``search_products``. It queries Meilisearch
first and, if Meili is unreachable, falls back to a Postgres ``icontains`` query so
search always returns *something* — degraded beats broken (plan.md §7).
"""

from __future__ import annotations

from django.db.models import Q

from apps.catalog.services import active_products

from . import client


def _postgres_fallback(query: str, *, limit: int, offset: int) -> tuple[list, int]:
    qs = (
        active_products()
        .filter(
            Q(name__icontains=query)
            | Q(description__icontains=query)
            | Q(category__name__icontains=query)
            | Q(tags__name__icontains=query)
        )
        .distinct()
    )
    total = qs.count()
    products = list(qs[offset : offset + limit])
    hits = [
        {
            "id": str(p.id),
            "name": p.name,
            "slug": p.slug,
            "category": p.category.name,
            "category_slug": p.category.slug,
            "price_from": float(p.price_from),
            "thumbnail": (p.images.all()[0].image.url if p.images.all() else None),
        }
        for p in products
    ]
    return hits, total


def search_products(query: str, *, limit: int, offset: int = 0) -> dict:
    """Return {"hits": [...], "total": int, "engine": "meili"|"postgres"}.

    Hits carry only the minimal fields the dropdown/cards need — never a full
    product payload.
    """
    query = (query or "").strip()
    if not query:
        return {"hits": [], "total": 0, "engine": "none"}

    result = client.raw_search(query, limit=limit, offset=offset)
    if result is not None:
        hits = [
            {
                "id": h.get("id"),
                "name": h.get("name"),
                "slug": h.get("slug"),
                "category": h.get("category"),
                "category_slug": h.get("category_slug"),
                "price_from": h.get("price_from"),
                "thumbnail": h.get("thumbnail"),
            }
            for h in result.get("hits", [])
        ]
        total = result.get("estimatedTotalHits", len(hits))
        return {"hits": hits, "total": total, "engine": "meili"}

    hits, total = _postgres_fallback(query, limit=limit, offset=offset)
    return {"hits": hits, "total": total, "engine": "postgres"}

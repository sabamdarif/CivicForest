"""Thin Meilisearch wrapper.

Isolates the SDK behind a small surface so the rest of the app never imports
``meilisearch`` directly, and so a Meili outage degrades to a Postgres fallback
(see ``services.py``) instead of raising into the request path (plan.md §7).
"""

from __future__ import annotations

import logging

from django.conf import settings

logger = logging.getLogger(__name__)

PRODUCTS_INDEX = f"{settings.MEILISEARCH_INDEX_PREFIX}_products"

# Search relevance: name outranks category/description (plan.md §7).
SEARCHABLE_ATTRIBUTES = ["name", "category", "tags", "description"]
FILTERABLE_ATTRIBUTES = ["category_slug", "sizes", "colors", "is_new", "is_bestseller"]
SORTABLE_ATTRIBUTES = ["price_from", "created_at"]


def get_client():
    """Return a configured Meilisearch client, or None if the SDK/URL is absent."""
    try:
        import meilisearch
    except ImportError:  # pragma: no cover - SDK optional at runtime
        return None
    if not settings.MEILISEARCH_URL:
        return None
    return meilisearch.Client(settings.MEILISEARCH_URL, settings.MEILISEARCH_MASTER_KEY or None)


def ensure_index() -> bool:
    """Create the products index and apply settings. Returns True on success."""
    client = get_client()
    if client is None:
        return False
    try:
        client.create_index(PRODUCTS_INDEX, {"primaryKey": "id"})
        index = client.index(PRODUCTS_INDEX)
        index.update_searchable_attributes(SEARCHABLE_ATTRIBUTES)
        index.update_filterable_attributes(FILTERABLE_ATTRIBUTES)
        index.update_sortable_attributes(SORTABLE_ATTRIBUTES)
        return True
    except Exception:  # noqa: BLE001 - never let indexing setup break a request
        logger.warning("Meilisearch ensure_index failed", exc_info=True)
        return False


def upsert_documents(documents: list[dict]) -> bool:
    client = get_client()
    if client is None or not documents:
        return False
    try:
        client.index(PRODUCTS_INDEX).add_documents(documents)
        return True
    except Exception:  # noqa: BLE001
        logger.warning("Meilisearch upsert failed", exc_info=True)
        return False


def delete_document(doc_id: str) -> bool:
    client = get_client()
    if client is None:
        return False
    try:
        client.index(PRODUCTS_INDEX).delete_document(doc_id)
        return True
    except Exception:  # noqa: BLE001
        logger.warning("Meilisearch delete failed", exc_info=True)
        return False


def raw_search(query: str, *, limit: int, offset: int = 0) -> dict | None:
    """Run a search. Returns None (not an exception) if Meili is unreachable so the
    caller can fall back to Postgres."""
    client = get_client()
    if client is None:
        return None
    try:
        return client.index(PRODUCTS_INDEX).search(query, {"limit": limit, "offset": offset})
    except Exception:  # noqa: BLE001
        logger.info("Meilisearch query failed; caller should fall back", exc_info=True)
        return None

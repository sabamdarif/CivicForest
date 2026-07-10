"""Celery tasks that keep the search index eventually-consistent with Postgres.

The write path is never synchronously coupled to Meili: catalog signals enqueue these
tasks, and a nightly full resync is the safety net for any missed signal (plan.md §7).
"""

from __future__ import annotations

import logging

from celery import shared_task

from apps.catalog.models import Product

from . import client
from .documents import product_to_document

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=10)
def index_product(self, product_id: str) -> None:
    product = (
        Product.objects.filter(id=product_id)
        .select_related("category", "material")
        .prefetch_related("variants", "images", "tags")
        .first()
    )
    if product is None or not product.is_active:
        client.delete_document(str(product_id))
        return
    if not client.upsert_documents([product_to_document(product)]):
        # Meili down. When running eagerly (tests / no-worker dev) there is no broker
        # to retry against, and the nightly reindex is the safety net — so just skip.
        if self.request.is_eager:
            return
        # Otherwise retry with backoff; the Postgres fallback covers reads meanwhile.
        raise self.retry()


@shared_task
def remove_product(product_id: str) -> None:
    client.delete_document(str(product_id))


@shared_task
def reindex_all() -> int:
    """Full resync — nightly safety net and manual `reindex_search` command."""
    client.ensure_index()
    products = (
        Product.objects.filter(is_active=True)
        .select_related("category", "material")
        .prefetch_related("variants", "images", "tags")
    )
    documents = [product_to_document(p) for p in products]
    client.upsert_documents(documents)
    return len(documents)

"""Catalog write signals → async index sync.

Registered from ``CatalogConfig.ready``. Each handler only *enqueues* a Celery task
so the transactional write path never blocks on Meilisearch.
"""

from __future__ import annotations

from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from apps.catalog.models import Category, Product, ProductImage, ProductVariant, Tag

from .tasks import index_product, remove_product


@receiver(post_save, sender=Product)
def on_product_saved(sender, instance: Product, **kwargs):
    index_product.delay(str(instance.id))


@receiver(post_delete, sender=Product)
def on_product_deleted(sender, instance: Product, **kwargs):
    remove_product.delay(str(instance.id))


@receiver(post_save, sender=ProductVariant)
@receiver(post_delete, sender=ProductVariant)
def on_variant_changed(sender, instance: ProductVariant, **kwargs):
    # Stock/price/color changes alter the denormalized document.
    index_product.delay(str(instance.product_id))


@receiver(post_save, sender=ProductImage)
@receiver(post_delete, sender=ProductImage)
def on_image_changed(sender, instance: ProductImage, **kwargs):
    index_product.delay(str(instance.product_id))


@receiver(post_save, sender=Category)
@receiver(post_delete, sender=Category)
@receiver(post_save, sender=Tag)
@receiver(post_delete, sender=Tag)
def on_taxonomy_changed(sender, instance, **kwargs):
    # Category/tag names are denormalized into product documents — a rename would
    # otherwise stay stale until a manual reindex (bugs.md #17).
    for product_id in instance.products.values_list("id", flat=True):
        index_product.delay(str(product_id))

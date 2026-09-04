"""Catalogue edits mark search documents stale. Nothing here builds one.

Marking is a single UPDATE with no vector work, so it is safe in any request (M3 task 3). What
rebuilds a marked document is ``reindex_search``, or the admin save path for the one product a
staff member just edited.

The three vocabularies use ``pre_delete`` rather than ``post_delete`` on purpose: once the row
is gone so are its relations, and the affected products can no longer be found.
"""

from django.db.models import Q
from django.db.models.signals import post_delete, post_save, pre_delete
from django.dispatch import receiver

from apps.catalog.models import Category, Collection, Product, ProductVariant, Tag

from .models import SearchDocument


def _mark(*conditions, **lookups) -> None:
    """``updated_at`` is deliberately not touched: it records when a document was last built."""
    SearchDocument.objects.filter(*conditions, **lookups).update(is_stale=True)


@receiver(post_save, sender=Product)
def product_saved(sender, instance, **kwargs):
    """Firing before the product's tags and collections are written is fine: the rebuild reads
    current data, so marking is order-independent."""
    _mark(product=instance)


@receiver([post_save, post_delete], sender=ProductVariant)
def variant_changed(sender, instance, **kwargs):
    # A variant carries the colours in the C tier, so adding or retiring one changes the document.
    _mark(product_id=instance.product_id)


@receiver([post_save, pre_delete], sender=Category)
def category_changed(sender, instance, **kwargs):
    # A product's own category and its parent are both in the B tier.
    _mark(Q(product__category=instance) | Q(product__category__parent=instance))


@receiver([post_save, pre_delete], sender=Collection)
def collection_changed(sender, instance, **kwargs):
    _mark(product__collections=instance)


@receiver([post_save, pre_delete], sender=Tag)
def tag_changed(sender, instance, **kwargs):
    _mark(product__tags=instance)

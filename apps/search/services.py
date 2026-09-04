"""Search services: building the document a query will read.

The document is denormalised on purpose: one row per product, so a query never joins across the
catalogue mid-request. ``text`` is deliberately short, because it is what trigram matching reads
and ``word_similarity()`` against a whole description would never clear a floor.

Money never appears here except through ``catalog.services.card_data``, which is the one place a
product is mapped for display.
"""

from django.contrib.postgres.search import SearchVector
from django.db import connection
from django.db.models import Value
from django.utils import timezone

from apps.catalog import services as catalog

from .models import SearchDocument

CONFIG = "english"  # the stored vector and every query must agree on the dictionary


def _parts(product) -> tuple[str, str, str, str]:
    """The four weighted tiers: name A, taxonomy B, tags, material and colours C, body D.

    Colours are in C beyond what task 2 lists, because "black hoodie" is an ordinary query and
    a colour exists only on a variant. Sizes stay out: M and L as search tokens are noise.
    """
    category = product.category
    taxonomy = [category.name] if category else []
    if category and category.parent:
        taxonomy.append(category.parent.name)
    taxonomy += [collection.name for collection in product.collections.all()]

    facets = [tag.name for tag in product.tags.all()]
    if product.material:
        facets.append(product.material.name)
    facets += sorted({variant.color for variant in product.variants.all() if variant.color})

    return product.name, " ".join(taxonomy), " ".join(facets), product.description


def _weighted(text: str, weight: str) -> SearchVector:
    return SearchVector(Value(text), weight=weight, config=CONFIG)


def refresh(product) -> None:
    """Rebuild one product's document.

    Called from the admin save path and from ``reindex_search``, never from a customer request
    (M3 task 3). The vector is an expression, so it is written with an UPDATE: an INSERT cannot
    carry one.
    """
    name, taxonomy, facets, body = _parts(product)
    fields = {
        # Short on purpose: word_similarity() against a whole description would never clear
        # the floor, and this column is what typo tolerance and the SQLite path both read.
        "text": " ".join(part for part in (name, taxonomy, facets) if part),
        "is_stale": False,
        "updated_at": timezone.now(),
    }
    if connection.vendor == "postgresql":
        fields["vector"] = (
            _weighted(name, "A")
            + _weighted(taxonomy, "B")
            + _weighted(facets, "C")
            + _weighted(body, "D")
        )
    document, _ = SearchDocument.objects.get_or_create(product=product)
    SearchDocument.objects.filter(pk=document.pk).update(**fields)


def indexable():
    """Products a document is built from, with everything ``_parts`` reads prefetched."""
    return catalog.active_products().prefetch_related("collections")

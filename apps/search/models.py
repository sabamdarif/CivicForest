"""Search: the one document per product, the synonym table and the query log.

Two invariants. ``SearchDocument.text`` is deliberately short (name, taxonomy, tags, material,
colours and not the description), because ``word_similarity()`` against a long blob never clears
a similarity floor and that column is what typo tolerance reads. And ``vector`` is Postgres
only: the query path in `services.py` degrades to ``text__icontains`` on SQLite so local
development still works (A10).
"""

from django.contrib.postgres.indexes import GinIndex
from django.contrib.postgres.search import SearchVectorField
from django.db import models

from apps.catalog.models import Product
from apps.common.models import UUIDTimestampedModel

# The search field's maxlength, the serializer's cap and the logged column are one number.
MAX_QUERY_LENGTH = 60


class SearchDocument(UUIDTimestampedModel):
    """One denormalised row per product: the weighted vector and the trigram blob.

    ``is_stale`` is set by the signals in `signals.py` and cleared by ``reindex_search``, and
    ``updated_at`` records when the document was last built, because marking it stale does not
    touch it. Nothing rebuilds a document inside a customer request (M3 task 3).
    """

    product = models.OneToOneField(
        Product, on_delete=models.CASCADE, related_name="search_document"
    )
    vector = SearchVectorField(null=True, editable=False)
    text = models.TextField(blank=True, editable=False)
    is_stale = models.BooleanField(default=True)

    class Meta:
        ordering = ["-created_at"]
        # Postgres builds a GIN index; SQLite's index template has no USING clause, so the
        # same migration leaves it a plain index there rather than failing.
        indexes = [GinIndex(fields=["vector"], name="search_document_vector_gin")]

    def __str__(self):
        return f"Document for {self.product.name}"


class SearchSynonym(UUIDTimestampedModel):
    """One equivalence group, admin-editable (decision 6).

    Expansion is symmetric: a query matching ``term`` or any member of ``expansion`` searches
    for all of them. One row `t-shirt -> tshirt, tee, tees` therefore covers every direction
    instead of needing a row per spelling.
    """

    term = models.CharField(max_length=60, unique=True)
    expansion = models.CharField(
        max_length=240, help_text="Comma-separated equivalents, e.g. tshirt, tee, tees"
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["term"]

    def __str__(self):
        return f"{self.term} -> {self.expansion}"


class SearchQueryLog(UUIDTimestampedModel):
    """What was searched and how much it found (D9).

    One row per submitted query, so a count answers "how many people searched this". M8
    surfaces the zero-result terms (O1, O13) and the suggest endpoint reads the popular ones.
    """

    query = models.CharField(max_length=MAX_QUERY_LENGTH, db_index=True)
    result_count = models.PositiveIntegerField(default=0)
    session_key = models.CharField(max_length=64, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.query} ({self.result_count})"

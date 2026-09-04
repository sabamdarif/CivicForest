"""Ranking, weighting and typo tolerance: the assertions only Postgres can answer.

Skipped in the offline SQLite run, which is why they are gathered in one module rather than
sprinkled through the others. CI runs against postgres:17-alpine, so this is where the "hoodei
finds hoodies" criterion is actually proved.
"""

import pytest
from django.core.management import call_command
from django.db import connection
from django.http import QueryDict

from apps.catalog import services as catalog
from apps.catalog.models import Tag
from apps.search import services
from apps.search.models import SearchDocument

pytestmark = [
    pytest.mark.django_db,
    pytest.mark.skipif(
        connection.vendor != "postgresql", reason="tsvector, SearchRank and pg_trgm are Postgres"
    ),
]


def _matches(term: str) -> list[str]:
    rank = services.ranking(term)
    if rank is None:
        return []
    products = catalog.ranked(catalog.active_products(), rank).order_by(
        *catalog.order_for(catalog.DEFAULT_SORT, rank)
    )
    return [product.name for product in products]


@pytest.fixture(autouse=True)
def documents(catalogue):
    call_command("reindex_search")
    return catalogue


def test_a_typo_still_finds_the_product(documents):
    assert "Green Hoodie" in _matches("hoodei")
    assert "Green Hoodie" in _matches("hoddie")


def test_a_half_typed_word_matches_as_a_prefix(documents):
    # "hood" does not stem to "hoodie", so this is the prefix tier rather than the dictionary.
    assert "Green Hoodie" in _matches("hood")


def test_the_fuzzy_tier_stays_out_when_the_words_as_typed_match(documents):
    # Both words are in one document and nowhere else. If the trigram tier were unioned in
    # rather than held back, the tees would ride along on their similarity to the whole phrase.
    assert _matches("black hoodie") == ["Green Hoodie"]


def test_the_fuzzy_tier_rescues_a_query_that_would_otherwise_be_empty(documents):
    assert _matches("hoodie") == _matches("hoodei")


def test_the_name_outranks_the_description_and_the_bestseller_flag(documents):
    bestseller = documents["printed"]
    assert bestseller.is_bestseller
    bestseller.description = "Wear it under a hoodie"
    bestseller.save()
    call_command("reindex_search", stale=True)

    names = _matches("hoodie")

    # A in the document beats D, and a real rank leads relevance ahead of featured order.
    assert names.index("Green Hoodie") < names.index("Graphic Tee")


def test_the_stored_vector_carries_the_weights(documents):
    vector = SearchDocument.objects.get(product=documents["hoodie"]).vector

    assert ":1A" in vector  # the first word of the name
    assert "B" in vector and "C" in vector


def test_did_you_mean_is_trigram_output_or_nothing(documents):
    assert services.did_you_mean("hoodei") == "Hoodies"
    assert services.did_you_mean("cottn") == "Cotton"
    # Nothing invented (J9), and never the word already typed.
    assert services.did_you_mean("zzzzqqq") == ""
    assert services.did_you_mean("hoodies") == ""


def test_the_zero_result_page_offers_the_suggestion_as_a_link(client, documents):
    # A vocabulary word no live product carries is the case that reaches this page at all: the
    # trigram tier is generous enough that a near-miss usually finds products instead.
    Tag.objects.create(name="Corduroy")

    body = client.get("/search/?q=cordroy").content.decode()

    assert "No results for" in body
    assert "Did you mean" in body
    assert 'href="/search/?q=Corduroy"' in body


def test_relevance_falls_back_to_featured_order_without_a_query(documents):
    listed = catalog.product_list(catalog.parse_filters(QueryDict("")))
    assert [product.name for product in listed.page.object_list][0] == "Graphic Tee"

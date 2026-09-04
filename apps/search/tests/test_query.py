"""The query path: what a typed term matches, and what it cannot be made to do.

Backend-independent assertions only. Ranking and typo tolerance are Postgres-only and live in
`test_ranking_postgres.py`; what is checked here is that the same restriction, the same synonym
expansion and the same guards hold on either backend.
"""

import pytest
from django.core.management import call_command
from django.http import QueryDict

from apps.catalog import services as catalog
from apps.search import services
from apps.search.models import SearchSynonym

pytestmark = pytest.mark.django_db


def _matches(term: str) -> list[str]:
    """Product names a term finds, in relevance order."""
    rank = services.ranking(term)
    if rank is None:
        return []
    products = catalog.ranked(catalog.active_products(), rank).order_by(
        *catalog.order_for(catalog.DEFAULT_SORT, rank)
    )
    return [product.name for product in products]


def _filters(term: str, **params) -> dict:
    filters = catalog.parse_filters(QueryDict("&".join(f"{k}={v}" for k, v in params.items())))
    filters["q"] = services.clean(term)
    filters["ranking"] = services.ranking(term)
    return filters


@pytest.fixture(autouse=True)
def documents(catalogue):
    call_command("reindex_search")
    return catalogue


@pytest.mark.parametrize("term", ["", "   ", None, "!!!", "-"])
def test_nothing_to_search_for_is_not_a_search(term):
    assert services.ranking(term) is None


def test_a_name_and_a_category_both_match():
    assert "Green Hoodie" in _matches("hoodie")
    assert "Green Hoodie" in _matches("Hoodies")


def test_a_colour_is_searchable_because_it_is_in_the_document():
    assert "Green Hoodie" in _matches("black")


def test_the_shipped_synonym_group_matches_in_every_direction():
    # The row ships in a migration, so this is the "Done when" criterion, not a fixture.
    for term in ("tshirt", "t-shirt", "tee", "tees"):
        assert "Plain Tee" in _matches(term), term


def test_a_synonym_expands_from_any_member_of_its_group():
    SearchSynonym.objects.create(term="hoodie", expansion="hood, sweatshirt")
    assert "Green Hoodie" in _matches("sweatshirt")


def test_a_retired_synonym_stops_expanding():
    SearchSynonym.objects.create(term="hoodie", expansion="sweatshirt", is_active=False)
    # Not an empty result set: with the row off the term is no longer a hoodie, but the trigram
    # tier still offers whatever is loosely similar, ranked below any real match.
    assert "Green Hoodie" not in _matches("sweatshirt")


def test_an_inactive_product_is_not_searchable():
    assert _matches("retired") == []


@pytest.mark.parametrize(
    "hostile",
    [
        "'; drop table catalog_product; --",
        "hoodie & | ! ( ) :*",
        "<script>alert(1)</script>",
        "%_%",
        "x" * 500,
    ],
)
def test_a_hostile_query_is_answered_rather_than_raised(hostile):
    _matches(hostile)  # tokens are alnum-only, so no tsquery can be malformed


def test_the_term_is_capped_before_it_reaches_a_query():
    assert len(services.clean("x" * 500)) == 60
    assert services.clean("  two   words  ") == "two words"


def test_facet_counts_are_scoped_to_the_query():
    results = catalog.product_list(_filters("hoodie"))

    assert results.page.paginator.count == 1
    categories = {facet.value: facet.count for facet in results.facets["category"]}
    assert categories == {"hoodies": 1}
    # And the sidebar still offers only what the query can reach.
    assert {facet.value for facet in results.facets["material"]} == {"fleece"}


def test_a_filter_narrows_a_query_rather_than_replacing_it():
    empty = catalog.product_list(_filters("hoodie", size="XL"))
    assert empty.page.paginator.count == 0

    kept = catalog.product_list(_filters("hoodie", size="L"))
    assert kept.page.paginator.count == 1


def test_the_term_leads_every_url_the_page_builds():
    filters = _filters("hoodie", size="L")

    assert catalog.filter_pairs(filters)[0] == ("q", "hoodie")
    assert catalog.query_string(filters) == "q=hoodie&size=L"
    assert "q=hoodie" in catalog.product_list(filters).chips[0].query


def test_relevance_is_the_only_sort_a_rank_touches():
    rank = services.ranking("hoodie")

    assert catalog.order_for("relevance", rank)[: len(rank.order_by)] == rank.order_by
    assert catalog.order_for("price-asc", rank) == catalog.SORTS["price-asc"]
    assert catalog.order_for("relevance", None) == catalog.SORTS["relevance"]

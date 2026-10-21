"""The two empty states: nothing typed yet, and a query that found nothing.

Neither may read like an error, and both have to offer a way forward (D8). The spelling
suggestion is trigram output, so its own assertions are in `test_ranking_postgres.py`.
"""

import pytest
from django.core.management import call_command

from apps.catalog.models import Product
from apps.search.models import SearchQueryLog

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def documents(catalogue):
    call_command("reindex_search")
    return catalogue


def _body(client, url: str) -> str:
    response = client.get(url)
    assert response.status_code == 200
    return response.content.decode()


def test_a_query_that_finds_nothing_offers_a_way_forward(client):
    body = _body(client, "/search/?q=zzzzqqq")

    assert "No results for “zzzzqqq”" in body
    assert "Popular right now" in body and "product-card" in body
    assert 'href="/shop/"' in body
    # An empty result set is not an error, so nothing on the page says one happened.
    assert "error" not in body.lower()


def test_nothing_typed_yet_prompts_rather_than_listing_the_catalogue(client):
    body = _body(client, "/search/")

    assert "Search the catalogue" in body
    assert "Popular right now" in body
    # /search/ is not a second copy of /shop/: no grid of everything, no filter panel.
    assert "filters__group" not in body


def test_a_filter_that_empties_the_page_offers_to_clear_itself(client):
    body = _body(client, "/search/?q=hoodie&size=XL")

    assert "Clear the filters" in body
    assert 'href="/search/?q=hoodie"' in body


def test_the_empty_state_is_the_same_whether_javascript_swapped_it(client):
    whole = _body(client, "/search/?q=zzzzqqq")
    partial = client.get("/search/?q=zzzzqqq", headers={"X-Partial": "shop"}).content.decode()

    assert "No results for" in whole and "No results for" in partial
    assert "<html" not in partial


def test_the_term_is_logged_so_the_back_office_learns_what_is_missing(client):
    _body(client, "/search/?q=corduroy trousers")

    row = SearchQueryLog.objects.get()
    assert (row.query, row.result_count) == ("corduroy trousers", 0)


def test_popular_falls_back_to_new_arrivals_when_nothing_is_flagged(client, documents):
    Product.objects.filter(is_bestseller=True).update(is_bestseller=False)

    body = _body(client, "/search/?q=zzzzqqq")

    assert "Popular right now" in body and "product-card" in body

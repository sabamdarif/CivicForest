"""The results page: the shop grid with a query on top, and the log row that records the query.

The point of most of these is that /search/ did not grow a second grid. What is asserted is that
the term survives every control the shop already had, and that one search writes one row.
"""

import re

import pytest
from django.core.management import call_command

from apps.catalog import services as catalog
from apps.search.models import SearchQueryLog

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def documents(catalogue):
    call_command("reindex_search")
    return catalogue


def _body(client, url: str) -> str:
    response = client.get(url)
    assert response.status_code == 200, f"{url} -> {response.status_code}"
    return response.content.decode()


def test_a_query_echoes_and_finds_its_product(client):
    body = _body(client, "/search/?q=hoodie")

    assert "You searched for" in body and "hoodie" in body
    assert "Green Hoodie" in body
    assert "1 result for" in body


def test_no_query_is_a_page_rather_than_an_error_or_a_redirect(client):
    # The header's search icon links straight here, so this has to stand on its own.
    for url in ("/search/", "/search/?q="):
        body = _body(client, url)
        assert "<h1>Search</h1>" in body
        assert 'name="q"' in body


def test_the_page_asks_not_to_be_indexed(client):
    assert '<meta name="robots" content="noindex,follow">' in _body(client, "/search/?q=hoodie")


def test_the_filter_form_posts_back_to_search_carrying_the_query(client):
    body = _body(client, "/search/?q=hoodie")

    assert re.search(r'<form class="filters" method="get" action="/search/"', body)
    assert '<input type="hidden" name="q" value="hoodie">' in body
    # Clearing the filters is not leaving the search.
    assert 'href="/search/?q=hoodie"' in body


def test_a_filter_a_sort_and_a_page_all_keep_the_query(client, monkeypatch):
    filtered = _body(client, "/search/?q=tee&size=M")
    assert "Plain Tee" in filtered and "Green Hoodie" not in filtered
    # The sort form carries the state it does not show, the term included.
    assert filtered.count('name="q" value="tee"') >= 2

    monkeypatch.setattr(catalog, "PAGE_SIZE", 1)
    paged = _body(client, "/search/?q=tee")
    assert re.search(r'href="\?page=2&(amp;)?q=tee', paged)


def test_the_sort_list_is_the_shops_own(client):
    body = _body(client, "/search/?q=tee")

    for _, label in catalog.sort_options():
        assert label in body


def test_a_partial_fetch_returns_the_region_and_nothing_else(client):
    response = client.get("/search/?q=hoodie", headers={"X-Partial": "shop"})

    body = response.content.decode()
    assert "<html" not in body
    assert 'class="shop__layout"' in body
    assert "X-Partial" in response.headers["Vary"]


def test_one_submitted_query_writes_one_row(client):
    _body(client, "/search/?q=hoodie")

    row = SearchQueryLog.objects.get()
    assert (row.query, row.result_count) == ("hoodie", 1)


def test_a_query_that_finds_nothing_is_logged_too(client):
    _body(client, "/search/?q=zzzzqqq")

    row = SearchQueryLog.objects.get()
    assert row.result_count == 0


def test_nothing_that_is_not_a_new_search_is_logged(client):
    _body(client, "/search/")
    _body(client, "/search/?q=")
    _body(client, "/search/?q=hoodie&page=2")
    client.get("/search/?q=hoodie", headers={"X-Partial": "shop"})

    assert SearchQueryLog.objects.count() == 0


def test_the_canonical_url_drops_the_query(client):
    body = _body(client, "/search/?q=hoodie&size=M")

    assert '<link rel="canonical" href="http://testserver/search/">' in body

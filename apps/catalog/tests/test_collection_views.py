"""The collections index and one collection (C7).

A collection detail page is the shop's own region with a different hero on top, so the test
that matters is that it stays the shop: same filters, same counts, same grid. If it ever grows
its own copy of any of that, the two will disagree about what matches.
"""

import re

import pytest
from django.test import Client

from apps.catalog.models import Collection

pytestmark = pytest.mark.django_db


@pytest.fixture
def client():
    return Client()


def _get(client, url: str) -> str:
    response = client.get(url)
    assert response.status_code == 200, url
    return response.content.decode()


def _names(body: str) -> list[str]:
    return re.findall(r'class="product-card__name"><a href="[^"]*">([^<]+)', body)


def test_the_index_lists_active_collections_in_the_order_staff_set(client, catalogue):
    Collection.objects.filter(slug="staples").update(display_order=1)
    Collection.objects.filter(slug="new-arrivals").update(display_order=2)

    body = _get(client, "/collections/")

    assert body.index("Staples") < body.index("New arrivals")


def test_the_index_counts_only_live_products(client, catalogue):
    body = _get(client, "/collections/")
    counts = dict(re.findall(r'collection-card__title">([^<]+)</h2>.*?(\d+) product', body, re.S))

    assert counts["New arrivals"] == "1", "the plain tee, and not the retired one"


def test_an_inactive_collection_is_neither_listed_nor_reachable(client, catalogue):
    Collection.objects.filter(slug="staples").update(is_active=False)

    assert "Staples" not in _get(client, "/collections/")
    assert client.get("/collections/staples/").status_code == 404


def test_a_collection_that_is_not_there_is_a_404(client, catalogue):
    assert client.get("/collections/nope/").status_code == 404


def test_the_index_says_so_rather_than_showing_an_empty_grid(client):
    body = _get(client, "/collections/")

    assert "No collections yet" in body
    assert "collection-card" not in body


def test_a_collection_page_shows_only_its_own_products(client, catalogue):
    body = _get(client, "/collections/staples/")

    assert _names(body) == ["Plain Tee"]
    assert "<h1>Staples</h1>" in body


def test_a_collection_page_is_the_shop_region_with_a_different_hero(client, catalogue):
    body = _get(client, "/collections/new-arrivals/")

    # Same panel, same counts, same chip that undoes the scope.
    assert 'class="filters"' in body and "filters__group" in body
    assert 'action="/shop/"' in body, "filtering hands off to the canonical URL"
    assert "Staples" not in _names(body)


def test_filters_still_apply_inside_a_collection(client, catalogue):
    assert _names(_get(client, "/collections/new-arrivals/?size=L")) == ["Plain Tee"]
    assert _names(_get(client, "/collections/new-arrivals/?size=XL")) == []


def test_the_collection_page_swaps_the_same_region_as_the_shop(client, catalogue):
    response = client.get("/collections/new-arrivals/", headers={"X-Partial": "shop"})
    body = response.content.decode()

    assert "<!doctype" not in body.lower()
    assert "filters__group" in body

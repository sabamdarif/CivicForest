"""Searching with no JavaScript at all, the way M2's storefront journey is tested.

Every step here is built from what the previous response actually contained: the icon's href, the
form's action, the checkbox's name and value. If searching ever needs a script to be navigable,
one of these steps stops finding its way forward (P6, D2).
"""

import re

import pytest
from django.core.management import call_command
from django.test import Client

pytestmark = pytest.mark.django_db


@pytest.fixture
def client():
    return Client()


@pytest.fixture(autouse=True)
def documents(catalogue):
    call_command("reindex_search")
    return catalogue


def _page(client, url: str) -> str:
    response = client.get(url)
    assert response.status_code == 200, f"{url} -> {response.status_code}"
    return response.content.decode()


def _form(body: str, css_class: str) -> str:
    """One form's markup, from its opening tag to its close."""
    match = re.search(rf'<form class="{css_class}[^"]*"(.*?)</form>', body, re.S)
    assert match, f"no form.{css_class} in the page"
    return match.group(1)


def test_a_visitor_searches_and_reaches_a_product_without_a_script(client):
    home = _page(client, "/")

    # The header's search icon is a link, not a script hook.
    icon = re.search(r'<a class="icon-btn" href="(/search/)"[^>]*aria-label="Search"', home)
    assert icon

    landing = _page(client, icon.group(1))
    field = _form(landing, "search-bar")
    assert 'method="get" action="/search/"' in landing
    assert re.search(r'name="q"', field)

    # A GET form with one text field is exactly this URL, which is what the browser would build.
    results = _page(client, "/search/?q=hoodie")
    product = re.findall(r'href="(/product/[^"#?]+)"', results)[0]

    assert "buy__name" in _page(client, product)


def test_filtering_a_search_keeps_the_search(client):
    results = _page(client, "/search/?q=tee")
    panel = _form(results, "filters")

    # The panel carries the term as a hidden input, so submitting it cannot drop the query.
    assert '<input type="hidden" name="q" value="tee">' in panel
    option = re.search(r'name="size"[^>]*value="([^"]+)"', panel).group(1)

    filtered = _page(client, f"/search/?q=tee&size={option}")

    assert "You searched for" in filtered
    assert f"size={option}" in filtered or "chip" in filtered


def test_sorting_a_search_keeps_the_search(client):
    results = _page(client, "/search/?q=tee")
    sort = _form(results, "sort")

    assert '<input type="hidden" name="q" value="tee">' in sort
    assert '<option value="price-asc"' in sort

    sorted_page = _page(client, "/search/?q=tee&sort=price-asc")
    names = re.findall(r'class="product-card__name"><a href="[^"]+">([^<]+)<', sorted_page)

    assert names == ["Plain Tee", "Graphic Tee"]  # 799 before 999
    assert "You searched for" in sorted_page


def test_paging_a_search_keeps_the_search(client, monkeypatch):
    from apps.catalog import services

    monkeypatch.setattr(services, "PAGE_SIZE", 1)
    results = _page(client, "/search/?q=tee")

    next_page = re.search(r'href="(\?page=2[^"]*)"', results).group(1).replace("&amp;", "&")
    assert "q=tee" in next_page

    assert "You searched for" in _page(client, f"/search/{next_page}")


def test_the_overlay_is_never_the_only_way_in(client):
    home = _page(client, "/")

    # The dialog is in the markup, but the page it duplicates is reachable and complete.
    assert 'id="search-overlay"' in home
    assert "search-bar__input" in _page(client, "/search/")

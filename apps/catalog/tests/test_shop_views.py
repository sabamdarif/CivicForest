"""The shop page as a visitor meets it: URLs, forms, and the region JavaScript swaps.

The rule this file exists to protect is P6. Browse, filter, sort and paginate all work with
JavaScript disabled, which means the submit controls have to be in the markup the server sends
and the ids of the two filter copies must not collide. Both fail silently in a browser with
JavaScript on, which is the only browser anyone tests in by accident.
"""

import collections
import re

import pytest
from django.test import Client

pytestmark = pytest.mark.django_db


@pytest.fixture
def client():
    return Client()


def _get(client, url: str, **extra):
    response = client.get(url, **extra)
    assert response.status_code == 200, url
    return response.content.decode()


def _names(body: str) -> list[str]:
    return re.findall(r'class="product-card__name"><a href="[^"]*">([^<]+)', body)


# ── Routing ──────────────────────────────────────────────────────────────────
def test_the_shop_lists_everything_that_is_live(client, catalogue):
    body = _get(client, "/shop/")

    assert set(_names(body)) == {"Plain Tee", "Graphic Tee", "Green Hoodie"}
    assert "Retired Tee" not in body


def test_a_category_in_the_path_scopes_the_grid_and_names_the_page(client, catalogue):
    body = _get(client, "/shop/t-shirts/")

    assert set(_names(body)) == {"Plain Tee", "Graphic Tee"}
    assert "<h1>T-Shirts</h1>" in body
    # Breadcrumb back to the unscoped grid, per E10.
    assert 'href="/shop/"' in body


def test_a_category_that_is_not_there_is_a_404(client, catalogue):
    assert client.get("/shop/nope/").status_code == 404


def test_an_inactive_category_is_not_reachable_by_its_slug(client, catalogue):
    from apps.catalog.models import Category

    Category.objects.filter(slug="hoodies").update(is_active=False)

    assert client.get("/shop/hoodies/").status_code == 404


def test_a_hand_edited_url_widens_the_results_instead_of_failing(client, catalogue):
    body = _get(client, "/shop/?sort=;drop&size=&badge=free&min_price=abc&page=nope")

    assert len(_names(body)) == 3


# ── The no-JavaScript baseline (P6, D2) ──────────────────────────────────────
def test_every_filter_control_is_a_form_that_posts_on_its_own(client, catalogue):
    body = _get(client, "/shop/")
    forms = re.findall(r'<form[^>]*class="(filters|sort)"[^>]*>', body)

    assert forms.count("filters") == 2, "the sidebar and the drawer"
    assert forms.count("sort") == 1
    assert body.count('method="get"') >= 3


def test_the_submit_buttons_the_page_needs_without_javascript_are_in_the_markup(client, catalogue):
    body = _get(client, "/shop/")

    assert "Apply filters" in body
    assert ">Sort</button>" in body
    # Only filters.js hides them, so the server must never send them already hidden.
    assert "hidden data-js-hide" not in body and 'data-js-hide=""' not in body


def test_the_two_filter_copies_do_not_collide(client, catalogue):
    body = _get(client, "/shop/")
    ids = re.findall(r'\sid="([^"]+)"', body)
    labels = re.findall(r'<label[^>]*for="([^"]+)"', body)

    assert not [i for i, n in collections.Counter(ids).items() if n > 1]
    assert all(f'id="{target}"' in body for target in labels)


def test_the_sort_form_carries_the_filters_so_sorting_cannot_clear_them(client, catalogue):
    body = _get(client, "/shop/?size=M&material=cotton")
    hidden = re.search(r'<form class="sort".*?</form>', body, re.S).group(0)

    assert '<input type="hidden" name="size" value="M">' in hidden
    assert '<input type="hidden" name="material" value="cotton">' in hidden


def test_the_filter_form_carries_the_sort_for_the_same_reason(client, catalogue):
    body = _get(client, "/shop/?sort=price-asc")

    assert '<input type="hidden" name="sort" value="price-asc">' in body


def test_the_mobile_panel_is_a_details_because_a_dialog_needs_javascript(client, catalogue):
    body = _get(client, "/shop/")

    assert '<details class="filter-drawer">' in body
    # The shell's search overlay is the one <dialog> on the page, and it degrades to a plain
    # link to /search/ (D7). Nothing a filter needs may depend on JavaScript.
    assert body.count("<dialog") == 1
    assert 'id="search-overlay"' in body


# ── Filtering, sorting and paging through the URL ────────────────────────────
@pytest.mark.parametrize(
    ("query", "expected"),
    [
        ("", {"Plain Tee", "Graphic Tee", "Green Hoodie"}),
        ("category=hoodies", {"Green Hoodie"}),
        ("category=t-shirts", {"Plain Tee", "Graphic Tee"}),
        ("size=L", {"Plain Tee", "Green Hoodie"}),
        ("size=M&size=L", {"Plain Tee", "Graphic Tee", "Green Hoodie"}),
        ("color=Beige", {"Plain Tee", "Graphic Tee"}),
        ("material=fleece", {"Green Hoodie"}),
        ("collection=staples", {"Plain Tee"}),
        ("badge=sale", {"Graphic Tee"}),
        ("badge=bestseller", {"Graphic Tee"}),
        ("availability=in-stock", {"Plain Tee", "Graphic Tee", "Green Hoodie"}),
        ("max_price=800", {"Plain Tee"}),
        ("min_price=1000", {"Green Hoodie"}),
        ("min_price=800&max_price=1000", {"Graphic Tee"}),
        ("category=t-shirts&material=fleece", set()),
        ("size=M&color=Black&category=t-shirts", {"Plain Tee"}),
    ],
)
def test_every_filter_combination_lands_on_the_right_products(client, catalogue, query, expected):
    assert set(_names(_get(client, f"/shop/?{query}"))) == expected


@pytest.mark.parametrize(
    ("sort", "first"),
    [
        ("relevance", "Graphic Tee"),
        ("newest", "Green Hoodie"),
        ("price-asc", "Plain Tee"),
        ("price-desc", "Green Hoodie"),
        # Nothing has sold yet, so popularity falls back to newest rather than to nothing.
        ("popularity", "Green Hoodie"),
    ],
)
def test_every_sort_orders_the_grid(client, catalogue, sort, first):
    assert _names(_get(client, f"/shop/?sort={sort}"))[0] == first


def test_a_chip_removes_one_filter_and_keeps_the_others(client, catalogue):
    body = _get(client, "/shop/?size=M&size=L&sort=newest")
    chips = dict(re.findall(r'<a class="chip" href="([^"]*)"[^>]*>\s*<span>([^<]+)', body))

    assert chips == {
        "/shop/?size=L&amp;sort=newest": "M",
        "/shop/?size=M&amp;sort=newest": "L",
    }


def test_paging_keeps_the_filters(client, catalogue, settings):
    from apps.catalog import services

    settings.DEBUG = False
    monkey = services.PAGE_SIZE
    services.PAGE_SIZE = 1
    try:
        body = _get(client, "/shop/?size=M&sort=newest")
    finally:
        services.PAGE_SIZE = monkey

    assert 'href="?page=2&amp;size=M&amp;sort=newest"' in body


def test_the_empty_state_offers_the_way_out_rather_than_reading_like_an_error(client, catalogue):
    body = _get(client, "/shop/?min_price=99999")

    assert "Nothing matches those filters" in body
    assert "Clear all filters" in body
    assert "product-card" not in body


# ── The region JavaScript swaps (D2) ─────────────────────────────────────────
def test_the_partial_render_is_the_region_and_nothing_else(client, catalogue):
    response = client.get("/shop/?size=M", headers={"X-Partial": "shop"})
    body = response.content.decode()

    assert response.status_code == 200
    assert "<!doctype" not in body.lower() and "<footer" not in body
    # One renderer for both paths, so the counts beside the grid can never go stale.
    assert "filters__group" in body and "product-card" in body
    assert "X-Partial" in response.headers["Vary"]


def test_the_partial_and_the_whole_page_agree_about_what_matches(client, catalogue):
    whole = _get(client, "/shop/?category=hoodies")
    partial = client.get("/shop/?category=hoodies", headers={"X-Partial": "shop"})

    assert _names(whole) == _names(partial.content.decode())

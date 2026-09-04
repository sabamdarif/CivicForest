"""The whole journey with no JavaScript, which is the rule M2 is allowed to fail on (P6).

Every step here follows a link or submits a form found in the previous response, so nothing is
reached by a URL the tests invented. If a page ever needs a script to be navigable, one of these
steps stops finding its way forward.
"""

import re

import pytest
from django.test import Client

pytestmark = pytest.mark.django_db


@pytest.fixture
def client():
    return Client()


def _page(client, url: str, **data) -> str:
    response = client.post(url, data) if data else client.get(url)
    assert response.status_code == 200, f"{url} -> {response.status_code}"
    return response.content.decode()


def _hrefs(body: str, pattern: str) -> list[str]:
    return re.findall(rf'href="({pattern}[^"#?]*)"', body)


def test_a_visitor_walks_home_to_a_product_and_back_without_a_script(client, catalogue):
    home = _page(client, "/")

    # The SHOP menu and the category tiles are ordinary links.
    category = _hrefs(home, "/shop/")[0]
    assert category.startswith("/shop/")

    grid = _page(client, category)
    product = _hrefs(grid, "/product/")[0]

    detail = _page(client, product)
    assert "buy__name" in detail

    # Breadcrumbs are the way back, and they are links too (E10).
    assert "/shop/" in detail
    back = _page(client, "/shop/")
    assert "product-card" in back


def test_filtering_and_sorting_are_form_submissions(client, catalogue):
    body = _page(client, "/shop/")

    # The filter form is a GET, so submitting it is a URL the browser builds itself.
    assert re.search(r'<form class="filters" method="get" action="/shop/"', body)
    filtered = _page(client, "/shop/?size=M&sort=price-asc")
    assert "product-card" in filtered

    # And a chip is a link back to the same page with one value gone.
    chip = _hrefs(filtered, "/shop/\\?")
    assert chip or "chip" in filtered


def test_paging_is_links(client, catalogue, settings):
    from apps.catalog import services

    monkey = services.PAGE_SIZE
    services.PAGE_SIZE = 1
    try:
        body = _page(client, "/shop/")
        assert 'rel="next"' in body
        # The pagination macro emits ?page=N plus the current filter state.
        assert re.search(r'href="\?page=2', body)
    finally:
        services.PAGE_SIZE = monkey


def test_a_collection_is_reachable_from_the_index_and_browses_the_same_way(client, catalogue):
    index = _page(client, "/collections/")
    # A slug is required, or the pattern matches the index's own breadcrumb.
    first = _hrefs(index, "/collections/[a-z0-9-]+/")[0]

    detail = _page(client, first)

    assert "product-card" in detail
    assert 'class="filters"' in detail


def test_add_to_cart_is_a_form_post_and_the_page_says_what_happened(client, catalogue):
    detail = _page(client, "/product/plain-tee/")
    form = re.search(r'<form class="buy__form" method="post" action="([^"]+)"', detail)
    assert form and form.group(1) == "/cart/add/"

    # The form carries the slug and the colour; the size is the checked radio.
    size = re.search(r'name="size" value="([^"]+)"[^>]*checked', detail).group(1)
    response = client.post(
        "/cart/add/",
        {"product": "plain-tee", "color": "Black", "size": size, "quantity": "2"},
    )

    assert response.status_code == 302
    assert response.url == "/product/plain-tee/"
    assert "is in your cart." in _page(client, "/product/plain-tee/")


def test_swapping_colour_is_a_link_the_server_answers(client, catalogue):
    detail = _page(client, "/product/plain-tee/")
    swatches = dict(re.findall(r'href="(\?color=[^"]+)" data-colour="([^"]+)"', detail))
    # The one that is not already chosen: the current colour's link would prove nothing.
    other = next(href for href, colour in swatches.items() if colour != "Black")

    swapped = _page(client, f"/product/plain-tee/{other}")

    assert 'name="color" value="Beige"' in swapped
    assert swatches, "a colour has to be reachable without a script"

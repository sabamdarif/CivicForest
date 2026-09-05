"""Both template engines render and share one set of stylesheets.

Jinja2 renders the pages this project owns; the Django Template Language renders what
allauth and the admin ship. A page that reaches a variable the environment does not
define fails here, because the test settings use StrictUndefined.
"""

import pytest
from django.template.loader import get_template
from django.test import Client

STYLESHEETS = ("css/tokens.css", "css/base.css", "css/components.css", "css/layout.css")


@pytest.mark.django_db
def test_home_renders_through_the_jinja2_engine():
    # The chrome reads the announcement bar, so rendering any page now touches the database.
    response = Client().get("/")

    assert response.status_code == 200
    body = response.content.decode()
    assert "premium menswear" in body
    assert "FREE SHIPPING ON ALL ORDERS ABOVE ₹999" in body
    for sheet in STYLESHEETS:
        assert sheet in body
    # The one page sheet a page may add on top of the shared four (P3).
    assert "css/home.css" in body


def test_the_django_engine_shell_loads_the_same_stylesheets():
    rendered = get_template("base.html", using="django").render({})

    for sheet in STYLESHEETS:
        assert sheet in rendered


@pytest.mark.django_db
def test_the_header_marks_the_page_you_are_on(rf):
    # The SHOP submenu reads the categories, so rendering the chrome touches the database.
    rendered = get_template("_partials/header.html").render({}, rf.get("/shop/"))

    for path in ("/shop/", "/customise/", "/collections/", "/about/", "/contact/", "/cart/"):
        assert f'href="{path}"' in rendered
    assert '<a class="nav__link" href="/shop/" aria-current="page">' in rendered


@pytest.mark.django_db
def test_the_cart_badge_counts_what_is_really_in_the_cart(catalogue):
    """The header reads the cart itself, through a Jinja2 global, because no view can pass a
    variable into the shell."""
    client = Client()
    empty = client.get("/").content.decode()

    assert "cart-link__count" not in empty
    assert 'aria-label="Cart, 0 items"' in empty

    variant = catalogue["plain"].variants.get(size="M", color="Black")
    client.post(
        "/cart/add/",
        {"product": "plain-tee", "size": variant.size, "color": variant.color, "quantity": "3"},
    )
    filled = client.get("/").content.decode()

    assert 'aria-label="Cart, 3 items"' in filled
    assert ">3</span>" in filled

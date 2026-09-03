"""Add to cart from the product page, which is a form post and nothing else (P6).

The adversarial cases are the ones a form invites: a quantity typed into the HTML, a size that
belongs to a different product, and a variant that is out of stock. All three have to be
decided on the server, because the only thing the client is trusted for is a slug, a size and
a colour.
"""

from decimal import Decimal

import pytest
from django.contrib.messages import get_messages
from django.test import Client

from apps.cart.models import Cart
from apps.catalog.models import Category, Product, ProductVariant

pytestmark = pytest.mark.django_db


@pytest.fixture
def client():
    return Client()


@pytest.fixture
def tee():
    category = Category.objects.create(name="T-Shirts", slug="t-shirts")
    product = Product.objects.create(
        name="Classic Black Tee",
        slug="classic-black-tee",
        category=category,
        base_price=Decimal("799"),
        hsn_code="61091000",
    )
    ProductVariant.objects.create(product=product, size="M", color="Black", stock_quantity=4)
    ProductVariant.objects.create(product=product, size="L", color="Black", stock_quantity=0)
    return product


@pytest.fixture
def other(tee):
    """A second product with a size the first one does not sell."""
    product = Product.objects.create(
        name="Forest Hoodie",
        slug="forest-hoodie",
        category=tee.category,
        base_price=Decimal("1499"),
        hsn_code="61102000",
    )
    ProductVariant.objects.create(product=product, size="XL", color="Green", stock_quantity=9)
    return product


def _post(client, **data):
    payload = {"product": "classic-black-tee", "size": "M", "color": "Black", "quantity": "1"}
    return client.post("/cart/add/", {**payload, **data})


def _line(client):
    cart = Cart.objects.filter(session_key=client.session.session_key).first()
    return cart.items.first() if cart else None


def _messages(response) -> list[str]:
    return [str(message) for message in get_messages(response.wsgi_request)]


def test_a_guest_can_add_to_cart_and_lands_back_on_the_product(client, tee):
    response = _post(client, quantity="2")

    assert response.status_code == 302
    assert response.url == "/product/classic-black-tee/"
    line = _line(client)
    assert (line.variant.size, line.quantity) == ("M", 2)


def test_the_confirmation_names_what_went_in(client, tee):
    response = _post(client)

    assert _messages(response) == ["Classic Black Tee, M in Black, is in your cart."]


def test_a_stock_refusal_says_how_many_are_left(client, tee):
    assert _messages(_post(client, quantity="9")) == ["Only 4 left in stock."]


def test_a_size_nobody_stocks_says_so_rather_than_failing_silently(client, tee):
    assert _messages(_post(client, size="XXL")) == ["Choose a size and colour that is available."]


def test_a_size_typed_in_lower_case_still_resolves(client, tee):
    _post(client, size="m", color="black")

    assert _line(client).variant.size == "M"


def test_an_out_of_stock_variant_is_refused(client, tee):
    response = _post(client, size="L")

    assert response.status_code == 302
    assert _line(client) is None


def test_asking_for_more_than_the_shelf_holds_is_refused(client, tee):
    _post(client, quantity="9")  # only 4 in stock

    assert _line(client) is None


def test_a_quantity_typed_into_the_form_is_clamped_not_trusted(client, tee):
    # Ten is G7's cap, and four is all the stock there is, so 500 cannot get past either.
    _post(client, quantity="500")
    assert _line(client) is None

    _post(client, quantity="0")
    assert _line(client).quantity == 1


def test_a_quantity_that_is_not_a_number_falls_back_to_one(client, tee):
    _post(client, quantity="; drop table")

    assert _line(client).quantity == 1


def test_a_size_from_another_product_cannot_be_bought_through_this_one(client, tee, other):
    response = _post(client, size="XL", color="Green")

    assert response.status_code == 302
    assert _line(client) is None, "the other product's variant must not be reachable"


def test_a_product_nobody_is_selling_is_a_404(client, tee):
    tee.is_active = False
    tee.save()

    assert _post(client).status_code == 404
    assert _post(client, product="ghost").status_code == 404


def test_the_route_only_answers_a_post(client, tee):
    assert client.get("/cart/add/").status_code == 405


def test_adding_the_same_line_twice_adds_up_rather_than_replacing(client, tee):
    _post(client, quantity="1")
    _post(client, quantity="2")

    assert _line(client).quantity == 3

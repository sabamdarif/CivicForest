"""The cart page and its forms, driven the way a browser with no JavaScript drives them (P6).

Every total on the page comes back from `price_cart`, so the adversarial cases here are the
ones that try to send a number instead of an id: a posted total, a posted unit price, a
quantity past the cap, and a variant id that is not a variant id.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from django.contrib.messages import get_messages
from django.test import Client, override_settings

from apps.cart.models import Cart, Coupon, Wishlist
from apps.common.factories import UserFactory

pytestmark = pytest.mark.django_db

PINNED = override_settings(SHIPPING_FLAT_RATE="79.00", FREE_SHIPPING_THRESHOLD="999.00")


@pytest.fixture
def browser():
    return Client()


@pytest.fixture
def tee(catalogue):
    return catalogue["plain"].variants.get(size="M", color="Black")


def _add(browser, variant, quantity=1):
    return browser.post(
        "/cart/add/",
        {
            "product": variant.product.slug,
            "size": variant.size,
            "color": variant.color,
            "quantity": str(quantity),
        },
    )


def _messages(response) -> list[str]:
    return [str(m) for m in get_messages(response.wsgi_request)]


def _cart(browser) -> Cart:
    return Cart.objects.get(session_key=browser.session.session_key, user__isnull=True)


# ─── The page ────────────────────────────────────────────────────────────────
def test_the_cart_page_prints_the_lines_and_the_server_computed_totals(browser, tee):
    _add(browser, tee, 2)

    body = browser.get("/cart/").content.decode()

    assert "Plain Tee" in body
    assert "Color: Black" in body and "Size: M" in body
    assert "₹1,598.00" in body  # 2 × 799, computed here and nowhere else
    assert "Includes GST of" in body


def test_an_empty_cart_says_so_instead_of_showing_a_zero_total(browser):
    body = browser.get("/cart/").content.decode()

    assert "Your cart is empty" in body
    assert "Order summary" not in body


@PINNED
def test_the_progress_bar_prints_the_real_shortfall(browser, tee):
    _add(browser, tee, 1)

    body = browser.get("/cart/").content.decode()

    # 999 threshold less a 799 subtotal. Nothing here is invented (G2, J9).
    assert "₹200" in body
    assert "more to get" in body


@PINNED
def test_the_bar_stops_asking_once_the_cart_qualifies(browser, tee):
    _add(browser, tee, 2)

    body = browser.get("/cart/").content.decode()

    assert "You qualify for free shipping" in body
    assert "more to get" not in body


def test_the_cross_sell_row_leaves_out_what_is_already_in_the_cart(browser, tee, catalogue):
    _add(browser, tee, 1)

    body = browser.get("/cart/").content.decode()
    assert "You may also like" in body
    row = body.split("You may also like", 1)[1]

    # The graphic tee shares the T-Shirts family; the tee in the cart is not suggested back.
    assert "Graphic Tee" in row
    assert "Plain Tee" not in row
    assert "Retired Tee" not in row  # inactive


# ─── The forms ───────────────────────────────────────────────────────────────
def test_the_stepper_steps_up_and_down_without_javascript(browser, tee):
    _add(browser, tee, 2)
    variant = str(tee.id)

    resp = browser.post("/cart/line/", {"variant": variant, "quantity": "2", "op": "inc"})
    assert resp.status_code == 302
    assert resp["Location"] == "/cart/"
    assert _cart(browser).items.get().quantity == 3

    browser.post("/cart/line/", {"variant": variant, "quantity": "3", "op": "dec"})
    assert _cart(browser).items.get().quantity == 2


def test_stepping_down_from_one_removes_the_line(browser, tee):
    _add(browser, tee, 1)

    browser.post("/cart/line/", {"variant": str(tee.id), "quantity": "1", "op": "dec"})

    assert _cart(browser).items.count() == 0


def test_remove_takes_the_line_out(browser, tee):
    _add(browser, tee, 2)

    browser.post("/cart/line/", {"variant": str(tee.id), "op": "remove"})

    assert _cart(browser).items.count() == 0


def test_clear_empties_the_cart_and_drops_the_coupon(browser, tee):
    Coupon.objects.create(code="SAVE10", discount_type="percent", value=Decimal("10"))
    _add(browser, tee, 2)
    browser.post("/cart/coupon/", {"code": "SAVE10"})

    browser.post("/cart/clear/")

    cart = _cart(browser)
    assert cart.items.count() == 0
    assert cart.coupon_id is None


def test_a_coupon_is_applied_and_removed_by_form_post(browser, tee):
    Coupon.objects.create(code="SAVE10", discount_type="percent", value=Decimal("10"))
    _add(browser, tee, 2)

    browser.post("/cart/coupon/", {"code": "SAVE10"})
    body = browser.get("/cart/").content.decode()
    assert "SAVE10" in body
    assert "₹159.80" in body  # 10% of 1598

    browser.post("/cart/coupon/", {"op": "remove"})
    assert _cart(browser).coupon_id is None


def test_a_bad_coupon_code_says_why_and_changes_nothing(browser, tee):
    _add(browser, tee, 1)

    resp = browser.post("/cart/coupon/", {"code": "NOPE"}, follow=True)

    assert "That coupon code isn't valid." in _messages(resp)
    assert _cart(browser).coupon_id is None


# ─── Move to wishlist (G4) ───────────────────────────────────────────────────
def test_a_guest_is_asked_to_sign_in_rather_than_sent_to_a_page_that_does_not_exist(browser, tee):
    _add(browser, tee, 1)

    resp = browser.post("/cart/line/", {"variant": str(tee.id), "op": "wishlist"}, follow=True)

    assert "Sign in to save items to your wishlist." in _messages(resp)
    assert Wishlist.objects.count() == 0
    assert _cart(browser).items.count() == 1  # still in the cart


def test_a_signed_in_customer_moves_the_line_to_their_wishlist(browser, tee):
    user = UserFactory()
    browser.force_login(user)
    _add(browser, tee, 1)

    browser.post("/cart/line/", {"variant": str(tee.id), "op": "wishlist"})

    assert Wishlist.objects.filter(user=user, product=tee.product).exists()
    assert Cart.objects.get(user=user).items.count() == 0


# ─── What a hand-edited form cannot do ───────────────────────────────────────
def test_a_posted_total_and_unit_price_are_ignored(browser, tee):
    _add(browser, tee, 2)

    browser.post(
        "/cart/line/",
        {
            "variant": str(tee.id),
            "quantity": "2",
            "total": "1.00",
            "unit_price": "1.00",
            "discount": "1000.00",
            "subtotal": "1.00",
            "tax": "0.00",
        },
    )
    body = browser.get("/cart/").content.decode()

    assert "₹1,598.00" in body
    assert "₹1.00" not in body


def test_a_quantity_past_the_cap_is_refused_with_a_reason(browser, catalogue):
    deep = catalogue["plain"].variants.get(size="M", color="Black")
    deep.stock_quantity = 50
    deep.save(update_fields=["stock_quantity"])
    _add(browser, deep, 5)

    resp = browser.post("/cart/line/", {"variant": str(deep.id), "quantity": "11"}, follow=True)

    assert "You can order at most 10 of one item." in _messages(resp)
    assert _cart(browser).items.get().quantity == 5


def test_a_variant_id_that_is_not_an_id_is_a_404(browser, tee):
    _add(browser, tee, 1)

    assert (
        browser.post("/cart/line/", {"variant": "; drop table", "op": "remove"}).status_code == 404
    )


def test_the_cart_routes_only_answer_a_post(browser):
    for path in ("/cart/line/", "/cart/clear/", "/cart/coupon/"):
        assert browser.get(path).status_code == 405


# ─── The drawer is the same response, in a dialog ────────────────────────────
def test_a_partial_post_returns_the_drawer_instead_of_a_redirect(browser, tee):
    resp = browser.post(
        "/cart/add/",
        {"product": "plain-tee", "size": "M", "color": "Black", "quantity": "1"},
        headers={"X-Partial": "cart"},
    )
    body = resp.content.decode()

    assert resp.status_code == 200
    assert 'id="cart-drawer"' in body
    assert "Plain Tee" in body
    assert "Proceed to checkout" in body
    assert "X-Partial" in resp["Vary"]


def test_the_drawer_and_the_page_agree_on_the_total(browser, tee):
    _add(browser, tee, 2)

    drawer = browser.post(
        "/cart/line/",
        {"variant": str(tee.id), "quantity": "2"},
        headers={"X-Partial": "cart"},
    ).content.decode()
    page = browser.get("/cart/").content.decode()

    assert "₹1,598.00" in drawer
    assert "₹1,598.00" in page


def test_the_shell_carries_an_empty_drawer_for_the_header_to_open(browser):
    body = browser.get("/shop/").content.decode()

    assert 'id="cart-drawer"' in body
    assert 'data-dialog-open="cart-drawer"' in body
    assert 'data-count="0"' in body
    assert "js/cart.js" in body
    # A link first, so the header still works with no JavaScript.
    assert 'class="icon-btn cart-link" href="/cart/"' in body


def test_the_cart_page_does_not_offer_a_drawer_of_itself(browser, tee):
    _add(browser, tee, 1)

    body = browser.get("/cart/").content.decode()

    assert 'data-dialog-open="cart-drawer"' not in body
    # The dialog is still in the shell, and still empty.
    assert 'data-count="0"' in body


# ─── Stock revalidation reaches the page (G9) ────────────────────────────────
def test_the_page_names_the_line_it_had_to_reduce(browser, tee):
    _add(browser, tee, 4)
    tee.stock_quantity = 2
    tee.save(update_fields=["stock_quantity"])

    body = browser.get("/cart/").content.decode()

    assert "Only 2 of Plain Tee, M in Black left" in body
    assert "₹1,598.00" in body  # re-priced at the quantity that is actually available

"""The wishlist: the heart on every card, the product page's save button, and the page (task 6).

Part 3 of the decision register keeps hearts on accounts rather than cookies, so the adversarial
cases are a guest posting one, a customer posting somebody else's product id, and a `next` that
points off this host.
"""

from __future__ import annotations

import pytest
from django.contrib.messages import get_messages
from django.test import Client

from apps.cart.models import Wishlist
from apps.common.factories import UserFactory

pytestmark = pytest.mark.django_db

URL = "/account/wishlist/"


@pytest.fixture
def browser():
    return Client()


def _messages(response) -> list[str]:
    return [str(m) for m in get_messages(response.wsgi_request)]


# ─── The page ────────────────────────────────────────────────────────────────
def test_a_guest_is_invited_to_sign_in_rather_than_redirected(browser):
    body = browser.get(URL).content.decode()

    assert "Sign in to see your wishlist" in body


def test_a_signed_in_customer_with_nothing_saved_is_told_how_to_save(browser):
    browser.force_login(UserFactory())

    body = browser.get(URL).content.decode()

    assert "Nothing saved yet" in body


def test_the_page_lists_what_was_hearted(browser, catalogue):
    user = UserFactory()
    browser.force_login(user)
    Wishlist.objects.create(user=user, product=catalogue["plain"])

    body = browser.get(URL).content.decode()

    assert "Plain Tee" in body
    assert "Green Hoodie" not in body


def test_one_customer_cannot_see_anothers_wishlist(browser, catalogue):
    other = UserFactory()
    Wishlist.objects.create(user=other, product=catalogue["plain"])
    browser.force_login(UserFactory())

    body = browser.get(URL).content.decode()

    assert "Plain Tee" not in body
    assert "Nothing saved yet" in body


# ─── The heart ───────────────────────────────────────────────────────────────
def test_the_heart_on_a_product_page_now_saves_it(browser, catalogue):
    user = UserFactory()
    browser.force_login(user)

    resp = browser.post(URL, {"product": str(catalogue["plain"].pk)}, follow=True)

    assert Wishlist.objects.filter(user=user, product=catalogue["plain"]).exists()
    assert "Plain Tee is saved to your wishlist." in _messages(resp)


def test_hearting_the_same_product_twice_takes_it_off_again(browser, catalogue):
    user = UserFactory()
    browser.force_login(user)

    browser.post(URL, {"product": str(catalogue["plain"].pk)})
    resp = browser.post(URL, {"product": str(catalogue["plain"].pk)}, follow=True)

    assert not Wishlist.objects.filter(user=user).exists()
    assert "Plain Tee is off your wishlist." in _messages(resp)


def test_a_guest_is_asked_to_sign_in_and_nothing_is_saved(browser, catalogue):
    resp = browser.post(URL, {"product": str(catalogue["plain"].pk)}, follow=True)

    assert Wishlist.objects.count() == 0
    assert "Sign in to save items to your wishlist." in _messages(resp)


def test_the_heart_sends_the_customer_back_where_they_came_from(browser, catalogue):
    browser.force_login(UserFactory())

    resp = browser.post(
        URL,
        {"product": str(catalogue["plain"].pk)},
        headers={"Referer": "/shop/?size=M&page=2"},
    )

    assert resp["Location"] == "/shop/?size=M&page=2"


def test_a_next_pointing_off_this_host_is_ignored(browser, catalogue):
    browser.force_login(UserFactory())

    resp = browser.post(
        URL, {"product": str(catalogue["plain"].pk), "next": "https://evil.example/steal"}
    )

    assert resp["Location"] == "/shop/"


def test_a_product_nobody_is_selling_cannot_be_hearted(browser, catalogue):
    browser.force_login(UserFactory())

    assert browser.post(URL, {"product": str(catalogue["hidden"].pk)}).status_code == 404
    assert browser.post(URL, {"product": "; drop table"}).status_code == 404


def test_the_heart_renders_on_a_card_and_on_the_product_page(browser, catalogue):
    grid = browser.get("/shop/").content.decode()
    detail = browser.get("/product/plain-tee/").content.decode()

    assert f'action="{URL}"' in grid
    assert f'action="{URL}"' in detail

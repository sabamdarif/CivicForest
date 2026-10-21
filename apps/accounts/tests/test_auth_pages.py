"""allauth's pages wear the site's chrome (task 3).

The whole point of the override in `templates/django/allauth/layouts/` is that allauth's own
~25 templates need no edit: they inherit the header, the footer, the search overlay and the
cart drawer from the Jinja2 partials the storefront uses, through the {% jinja_partial %} tag.
These tests are the regression surface for that, because the two engines can drift apart
silently: nothing else fails when the DTL shell loses the header.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.django_db

SHEETS = ("css/tokens.css", "css/base.css", "css/components.css", "css/layout.css")
CHROME = ("site-header", "site-footer", "search-overlay", "cart-drawer", "i-search")

ENTRANCE = ("/accounts/login/", "/accounts/signup/", "/accounts/password/reset/")
MANAGE = (
    "/accounts/email/",
    "/accounts/password/change/",
    "/accounts/2fa/",
    "/accounts/sessions/",
    "/accounts/3rdparty/",
    "/accounts/logout/",
)


@pytest.mark.parametrize("url", ENTRANCE)
def test_an_entrance_page_carries_the_whole_shell(browser, url):
    body = browser.get(url).content.decode()

    # DTL's {#...#} does not span lines, so a multi-line comment written that way would be
    # rendered into the page instead of dropped.
    assert body.lstrip().startswith("<!doctype html>")
    assert "Django Template Language twin" not in body
    for marker in SHEETS + CHROME:
        assert marker in body, marker
    # The one sheet the auth pages add, shared with the account area (§10).
    assert "css/account.css" in body


@pytest.mark.parametrize("url", ENTRANCE)
def test_an_entrance_page_is_the_split_layout_with_the_trust_strip(browser, url):
    body = browser.get(url).content.decode()

    assert 'class="auth__brand' in body
    assert 'class="auth__card"' in body
    assert "trust-strip" in body
    # allauth's own bare menu is replaced, not merely restyled.
    assert "Menu:" not in body


@pytest.mark.parametrize("url", MANAGE)
def test_a_manage_page_sits_inside_the_account_area(signed_in, url):
    body = signed_in.get(url).content.decode()

    assert "account-nav" in body
    assert 'href="/account/orders/"' in body
    # Security is what stays marked while the customer is on any allauth manage page.
    assert '<a class="account-nav__link" href="/account/security/" aria-current="page">' in body
    for marker in SHEETS + CHROME:
        assert marker in body, marker


def test_a_form_field_gets_a_real_label_and_the_sites_control_class(browser):
    body = browser.get("/accounts/login/").content.decode()

    assert '<label class="field__label" for="id_login">' in body
    assert 'class="field__control"' in body
    assert 'id="id_password"' in body


def test_a_rejected_login_says_so_where_it_can_be_seen(browser, customer):
    response = browser.post(
        "/accounts/login/", {"login": customer.email, "password": "not-the-password"}
    )
    body = response.content.decode()

    assert response.status_code == 200
    assert 'class="notice notice--error"' in body
    assert "not correct" in body


def test_a_message_is_printed_once_and_not_twice(signed_in):
    # The drawer is in the shell and renders notices when it is the response, so a page that
    # rendered both would print every message twice.
    body = signed_in.get("/accounts/email/").content.decode()

    assert body.count("Successfully signed in") == 1


def test_the_google_button_posts_rather_than_visiting_an_extra_page(browser):
    body = browser.get("/accounts/login/").content.decode()

    assert "Continue with Google" in body
    assert 'action="/accounts/google/login/?process=login" method="post"' in body


def test_the_next_parameter_survives_the_round_trip_to_google(browser):
    body = browser.get("/accounts/login/?next=/checkout/").content.decode()

    assert "next=%2Fcheckout%2F" in body

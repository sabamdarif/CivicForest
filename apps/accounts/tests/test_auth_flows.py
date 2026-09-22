"""The journeys: signup, verification, login, and the wall at checkout.

These are the adversarial cases Q1 asks for on an auth surface. Every one of them drives the real
forms, because that is the only way the session carries what allauth needs: a test that reaches for
``force_login`` proves nothing about a customer's session.
"""

from __future__ import annotations

import re

import pytest
from allauth.account.models import EmailAddress
from django.core import mail

from apps.cart.models import Cart, CartItem
from apps.common.factories import UserFactory

from .conftest import PASSWORD, sign_in, verified

pytestmark = pytest.mark.django_db

SIGNUP = "/accounts/signup/"
LOGIN = "/accounts/login/"
CHECKOUT = "/checkout/"


def sign_up(browser, email, password=PASSWORD):
    return browser.post(SIGNUP, {"email": email, "password1": password, "password2": password})


def confirm_from_email(browser):
    """Follow the emailed link the way a customer does. allauth confirms on POST, not on GET, so
    a mail scanner prefetching the link cannot verify an address."""
    link = re.search(r"https?://\S+/accounts/confirm-email/\S+/", mail.outbox[-1].body)
    assert link, mail.outbox[-1].body
    url = link.group(0).split("testserver")[-1]
    assert browser.get(url).status_code == 200
    return browser.post(url)


# ─── Signup and verification ─────────────────────────────────────────────────
def test_signup_sends_a_link_and_the_link_verifies_the_address(browser):
    response = sign_up(browser, "new@example.com")

    assert response.status_code == 302
    assert len(mail.outbox) == 1
    assert "confirm-email" in mail.outbox[0].body

    confirm_from_email(browser)

    assert EmailAddress.objects.get(email="new@example.com").verified


def test_confirming_the_address_sends_one_branded_welcome(browser):
    sign_up(browser, "welcome@example.com")
    confirm_from_email(browser)

    welcome = mail.outbox[-1]

    assert welcome.to == ["welcome@example.com"]
    assert welcome.subject == "[CivicForest Clothing] Welcome to CivicForest Clothing"
    # It rides the branded base every allauth email extends, and carries no discount code.
    assert "Thanks for shopping with CivicForest Clothing" in welcome.body
    assert "%" not in welcome.body


def test_signing_up_with_an_address_that_exists_does_not_admit_it(browser, customer):
    response = sign_up(browser, customer.email)
    body = response.content.decode() if response.status_code == 200 else ""

    # Same answer as a fresh signup: a redirect to "verification sent", nothing on the page or in
    # the response that separates a taken address from a new one.
    assert response.status_code == 302
    assert "already" not in body.lower()
    # The owner of the address is told instead, and no second account was made.
    assert len(mail.outbox) == 1
    assert mail.outbox[0].to == [customer.email]
    assert type(customer).objects.filter(email=customer.email).count() == 1


def test_an_unverified_account_cannot_sign_in(browser):
    sign_up(browser, "unverified@example.com")

    response = browser.post(LOGIN, {"login": "unverified@example.com", "password": PASSWORD})

    # allauth stops at the confirm-email page and leaves the session anonymous. It does not send
    # a second verification mail here: its own cooldown covers the one signup just sent.
    assert response.status_code == 302
    assert response["Location"] == "/accounts/confirm-email/"
    assert not browser.session.get("_auth_user_id")


# ─── Login ───────────────────────────────────────────────────────────────────
def test_a_wrong_password_and_an_unknown_account_are_indistinguishable(browser, customer):
    wrong = browser.post(LOGIN, {"login": customer.email, "password": "not-the-password"})
    unknown = browser.post(LOGIN, {"login": "nobody@example.com", "password": PASSWORD})

    assert wrong.status_code == unknown.status_code == 200
    assert _errors(wrong) == _errors(unknown)


def _errors(response) -> list[str]:
    return [str(e) for e in response.context["form"].errors.get("__all__", [])]


def test_the_eleventh_failed_login_in_five_minutes_is_refused(browser, customer):
    for _ in range(10):
        rejected = browser.post(LOGIN, {"login": customer.email, "password": "wrong"})
        assert rejected.status_code == 200

    refused = browser.post(LOGIN, {"login": customer.email, "password": "wrong"})

    assert "Too many failed login attempts" in refused.content.decode()
    # And the limit is on the attempt, not on the password: the right one is refused too.
    assert sign_in(browser, customer).status_code == 200


def test_a_next_pointing_off_this_host_is_ignored(browser, customer):
    response = sign_in(browser, customer, next="https://evil.example/steal")

    assert response.status_code == 302
    assert response["Location"] == "/account/"


def test_login_with_no_next_lands_on_the_account_dashboard(browser, customer):
    assert sign_in(browser, customer)["Location"] == "/account/"


# ─── The wall at checkout (decision 14, B2) ──────────────────────────────────
def _add_to_cart(browser, catalogue, quantity):
    variant = catalogue["plain"].variants.get(size="M", color="Black")
    response = browser.post(
        "/cart/add/",
        {
            "product": "plain-tee",
            "size": variant.size,
            "color": variant.color,
            "quantity": quantity,
        },
    )
    assert response.status_code == 302
    return variant


def test_a_guest_at_checkout_is_sent_to_login_and_brought_back(browser):
    response = browser.get(CHECKOUT)

    assert response.status_code == 302
    assert response["Location"] == f"{LOGIN}?next={CHECKOUT}"


def test_an_unverified_account_is_refused_at_checkout(browser):
    """B2 blocks checkout, not only login. An address that was verified once and is not any more,
    because the mailbox bounced or was reassigned, must not still get through."""
    user = verified(UserFactory(email="lapsed@example.com", password=PASSWORD))
    sign_in(browser, user)
    EmailAddress.objects.filter(user=user).update(verified=False)

    response = browser.get(CHECKOUT)

    # The decorator re-sends the verification mail, so its templates are in the list too.
    assert "account/verified_email_required.html" in [t.name for t in response.templates]


def test_the_guest_cart_survives_the_login_wall_with_quantities_summed(
    browser, catalogue, customer
):
    """The whole point of the wall: the customer signs in at checkout and finds what they were
    buying, added to whatever was already in their account's cart rather than replacing it."""
    variant = catalogue["plain"].variants.get(size="M", color="Black")
    CartItem.objects.create(cart=Cart.objects.create(user=customer), variant=variant, quantity=2)
    _add_to_cart(browser, catalogue, 3)

    assert browser.get(CHECKOUT)["Location"] == f"{LOGIN}?next={CHECKOUT}"
    assert sign_in(browser, customer, next=CHECKOUT)["Location"] == CHECKOUT

    body = browser.get(CHECKOUT).content.decode()

    assert Cart.objects.get(user=customer).items.get(variant=variant).quantity == 5
    assert "Subtotal (5 items)" in body
    assert not Cart.objects.filter(user__isnull=True).exists()


def test_the_journey_from_signup_to_checkout_keeps_the_cart(browser, catalogue):
    _add_to_cart(browser, catalogue, 2)

    sign_up(browser, "journey@example.com")
    confirm_from_email(browser)
    response = browser.post(
        LOGIN, {"login": "journey@example.com", "password": PASSWORD, "next": CHECKOUT}
    )

    assert response["Location"] == CHECKOUT
    assert "Subtotal (2 items)" in browser.get(CHECKOUT).content.decode()


def test_a_verified_customer_with_an_empty_cart_is_told_so(signed_in):
    assert "nothing to check out" in signed_in.get(CHECKOUT).content.decode()

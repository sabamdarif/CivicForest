"""The account area: rendering, per-user scoping, consent, and the DPDP data flows (task 6).

Driven through the real login form (the conftest `sign_in`), because the data pages sit behind
allauth's `reauthentication_required` and `force_login` leaves a session that never
authenticated, so it would be refused where a real customer is let through.
"""

from __future__ import annotations

import json

import pytest

from apps.accounts.models import Address, DataRequest
from apps.common.factories import OrderFactory, UserFactory

from .conftest import sign_in, verified

pytestmark = pytest.mark.django_db

PAGES = (
    "/account/",
    "/account/profile/",
    "/account/addresses/",
    "/account/security/",
    "/account/data/",
    "/account/orders/",
)


@pytest.mark.parametrize("url", PAGES)
def test_a_page_renders_for_a_signed_in_customer(signed_in, url):
    assert signed_in.get(url).status_code == 200


@pytest.mark.parametrize("url", PAGES)
def test_a_guest_is_sent_to_login(browser, url):
    response = browser.get(url)
    assert response.status_code == 302
    assert response["Location"] == f"/accounts/login/?next={url}"


def test_a_page_renders_for_staff(browser, staff):
    assert sign_in(browser, staff).status_code == 302
    assert browser.get("/account/").status_code == 200


# ─── one customer cannot reach another's rows ────────────────────────────────
def test_a_customer_cannot_open_another_customers_order(signed_in):
    other = verified(UserFactory(email="someone-else@example.com"))
    order = OrderFactory(user=other)
    assert signed_in.get(f"/account/orders/{order.order_number}/").status_code == 404


def test_a_customer_cannot_edit_another_customers_address(signed_in):
    other = verified(UserFactory(email="someone-else@example.com"))
    address = Address.objects.create(
        user=other,
        full_name="Other Buyer",
        phone="9999999999",
        line1="9 Other Road",
        city="Bengaluru",
        state="Karnataka",
        postal_code="560001",
    )
    assert signed_in.get(f"/account/addresses/{address.pk}/edit/").status_code == 404


def test_only_the_callers_own_orders_are_listed(signed_in, customer):
    mine = OrderFactory(user=customer)
    other = OrderFactory(user=verified(UserFactory(email="someone-else@example.com")))
    body = signed_in.get("/account/orders/").content.decode()
    assert mine.order_number in body
    assert other.order_number not in body


# ─── marketing consent defaults off (J9) ─────────────────────────────────────
def test_marketing_opt_in_renders_unticked(signed_in):
    body = signed_in.get("/account/profile/").content.decode()
    at = body.index('name="marketing_opt_in"')
    assert "checked" not in body[at - 80 : at + 80]


def test_only_a_posted_checkbox_turns_marketing_on(signed_in, customer):
    signed_in.post("/account/profile/", {"first_name": "Buyer", "last_name": "", "phone": ""})
    customer.refresh_from_db()
    assert customer.marketing_opt_in is False

    signed_in.post(
        "/account/profile/",
        {"first_name": "Buyer", "last_name": "", "phone": "", "marketing_opt_in": "on"},
    )
    customer.refresh_from_db()
    assert customer.marketing_opt_in is True


# ─── DPDP export and erasure (B8) ────────────────────────────────────────────
def test_the_export_returns_the_callers_own_data_only(signed_in, customer):
    OrderFactory(user=customer)
    OrderFactory(user=verified(UserFactory(email="someone-else@example.com")))

    response = signed_in.post("/account/data/export/")
    assert response.status_code == 200
    assert response["Content-Type"] == "application/json"
    payload = json.loads(response.content)

    assert payload["account"]["email"] == customer.email
    assert len(payload["orders"]) == 1
    assert DataRequest.objects.filter(user=customer, kind=DataRequest.Kind.EXPORT).exists()


def test_the_export_carries_no_reusable_credentials(signed_in):
    payload = json.loads(signed_in.post("/account/data/export/").content)
    assert "password hashes" in payload["credentials_omitted"]
    assert "password" not in json.dumps(payload["account"])


def test_export_and_erasure_refuse_a_guest(browser):
    assert browser.post("/account/data/export/").status_code == 302
    assert browser.post("/account/data/erasure/").status_code == 302


def test_an_erasure_request_is_recorded_once(signed_in, customer):
    signed_in.post("/account/data/erasure/")
    signed_in.post("/account/data/erasure/")
    assert (
        DataRequest.objects.filter(
            user=customer,
            kind=DataRequest.Kind.ERASURE,
            status=DataRequest.Status.OPEN,
        ).count()
        == 1
    )


def test_the_data_page_shows_a_pending_erasure(signed_in, customer):
    DataRequest.objects.create(user=customer, kind=DataRequest.Kind.ERASURE)
    body = signed_in.get("/account/data/").content.decode()
    assert "awaiting review" in body
    assert 'action="/account/data/erasure/"' not in body

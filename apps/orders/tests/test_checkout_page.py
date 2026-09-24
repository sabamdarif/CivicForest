"""The server-rendered checkout page: it must work as a form that posts and re-renders,
create the order and open a gateway order on a valid post, and refuse an unticked terms box.
Payment itself (the Razorpay modal) is out of scope here; fake mode stands in for the gateway.
"""

from decimal import Decimal

import pytest
from django.test import Client
from django.urls import reverse

from apps.cart.models import Cart, CartItem
from apps.orders.models import Order

pytestmark = pytest.mark.django_db


NEW_ADDRESS = {
    "phone": "9999999999",
    "saved_address": "",
    "full_name": "Test Buyer",
    "line1": "1 MG Road",
    "line2": "",
    "city": "Bengaluru",
    "state": "Karnataka",
    "postal_code": "560001",
}


@pytest.fixture
def client_for(user):
    # Checkout is behind verified_email_required, so the user needs a verified primary email.
    from allauth.account.models import EmailAddress

    EmailAddress.objects.create(user=user, email=user.email, primary=True, verified=True)

    def _login():
        c = Client()
        c.force_login(user)
        return c

    return _login


def _fill_cart(user, variant, qty=1):
    cart, _ = Cart.objects.get_or_create(user=user)
    CartItem.objects.create(cart=cart, variant=variant, quantity=qty)
    return cart


def test_checkout_page_renders_the_form(client_for, user, variant):
    _fill_cart(user, variant)
    resp = client_for().get("/checkout/")
    assert resp.status_code == 200
    assert b"Checkout" in resp.content


def test_a_client_supplied_total_is_ignored(client_for, user, variant):
    # variant is 800.00 each; the order total must come from server re-pricing, never a payload.
    _fill_cart(user, variant, qty=2)
    client_for().post(
        "/checkout/",
        {**NEW_ADDRESS, "accept_terms": "1", "total": "1.00", "subtotal": "1.00"},
    )
    order = Order.objects.get(user=user)
    assert order.total == Decimal("1600.00")


def test_valid_post_creates_order_and_redirects_to_pay(client_for, user, variant):
    _fill_cart(user, variant)
    resp = client_for().post("/checkout/", {**NEW_ADDRESS, "accept_terms": "1"})
    order = Order.objects.get(user=user)
    assert resp.status_code == 302
    assert resp.url == reverse("checkout-pay", args=[order.order_number])
    assert order.status == Order.Status.PAYMENT_PENDING
    assert order.rights_ack_text  # the consent snapshot was taken
    assert order.payments.count() == 1  # gateway order opened (fake mode)


def test_post_without_terms_is_rejected(client_for, user, variant):
    _fill_cart(user, variant)
    resp = client_for().post("/checkout/", NEW_ADDRESS)  # accept_terms omitted
    assert resp.status_code == 200
    assert Order.objects.filter(user=user).count() == 0


def test_pay_page_is_owner_scoped(client_for, user, other_user, variant):
    _fill_cart(user, variant)
    client_for().post("/checkout/", {**NEW_ADDRESS, "accept_terms": "1"})
    order = Order.objects.get(user=user)

    intruder = Client()
    intruder.force_login(other_user)
    assert intruder.get(reverse("checkout-pay", args=[order.order_number])).status_code == 404

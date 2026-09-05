"""The two cart sweeps (task 9): the thirty-day expiry (G6) and the reminder selection (G5).

The trap both share is that `Cart.updated_at` does not move when a line changes, so a cart edited
this morning can carry a month-old timestamp. Every case here is built to catch that.
"""

from __future__ import annotations

from io import StringIO

import pytest
from django.core.management import call_command
from django.utils import timezone

from apps.cart import services
from apps.cart.models import Cart, CartItem
from apps.common.factories import (
    CartFactory,
    GuestCartFactory,
    ProductVariantFactory,
    UserFactory,
)

pytestmark = pytest.mark.django_db


def _age(cart, **delta):
    """Backdate a cart and every line on it. `auto_now` has to be written around."""
    when = timezone.now() - timezone.timedelta(**delta)
    Cart.objects.filter(pk=cart.pk).update(updated_at=when)
    CartItem.objects.filter(cart=cart).update(updated_at=when)
    return cart


# ─── Expiry (G6) ─────────────────────────────────────────────────────────────
def test_a_cart_nobody_has_touched_for_a_month_is_swept():
    cart = _age(GuestCartFactory(), days=31)

    assert services.expire_dormant(500) == 1
    assert not Cart.objects.filter(pk=cart.pk).exists()


def test_a_cart_touched_last_week_survives():
    cart = _age(GuestCartFactory(), days=7)

    assert services.expire_dormant(500) == 0
    assert Cart.objects.filter(pk=cart.pk).exists()


def test_a_line_edited_today_keeps_an_old_cart_alive():
    # The bug this exists to catch: adding a line does not save the cart row, so updated_at on
    # the cart alone would call this dormant and delete a cart in use.
    cart = _age(GuestCartFactory(), days=40)
    CartItem.objects.create(cart=cart, variant=ProductVariantFactory(), quantity=1)

    assert services.expire_dormant(500) == 0
    assert Cart.objects.filter(pk=cart.pk).exists()


def test_sweeping_takes_the_lines_with_it():
    cart = GuestCartFactory()
    CartItem.objects.create(cart=cart, variant=ProductVariantFactory(), quantity=1)
    _age(cart, days=31)

    services.expire_dormant(500)

    assert CartItem.objects.count() == 0


def test_the_batch_bounds_one_run():
    for _ in range(3):
        _age(GuestCartFactory(), days=31)

    assert services.expire_dormant(2) == 2
    assert Cart.objects.count() == 1


def test_the_command_reports_what_it_did():
    _age(GuestCartFactory(), days=31)
    out = StringIO()

    call_command("expire_carts", stdout=out)

    assert "expired 1 cart(s)" in out.getvalue()


# ─── Reminder selection (G5) ─────────────────────────────────────────────────
def _abandoned(hours=5, **kwargs):
    cart = CartFactory(**kwargs)
    CartItem.objects.create(cart=cart, variant=ProductVariantFactory(), quantity=1)
    return _age(cart, hours=hours)


def test_a_signed_in_cart_left_for_four_hours_is_owed_a_reminder():
    cart = _abandoned()

    assert list(services.carts_awaiting_reminder()) == [cart]


def test_a_cart_touched_an_hour_ago_is_left_alone():
    _abandoned(hours=1)

    assert list(services.carts_awaiting_reminder()) == []


def test_an_empty_cart_is_not_worth_an_email():
    _age(CartFactory(), hours=5)

    assert list(services.carts_awaiting_reminder()) == []


def test_a_guest_cart_has_nowhere_to_write_to():
    cart = GuestCartFactory()
    CartItem.objects.create(cart=cart, variant=ProductVariantFactory(), quantity=1)
    _age(cart, hours=5)

    assert list(services.carts_awaiting_reminder()) == []


def test_one_reminder_per_cart_and_no_more():
    cart = _abandoned()
    cart.reminded_at = timezone.now()
    cart.save(update_fields=["reminded_at"])

    assert list(services.carts_awaiting_reminder()) == []


def test_each_cart_appears_once_however_many_lines_it_has():
    cart = CartFactory()
    for _ in range(3):
        CartItem.objects.create(cart=cart, variant=ProductVariantFactory(), quantity=1)
    _age(cart, hours=5)

    waiting = list(services.carts_awaiting_reminder())

    assert waiting == [cart]
    assert waiting[0].lines == 3


def test_the_command_lists_them_without_sending_anything(mailoutbox):
    user = UserFactory(email="left@example.com")
    _abandoned(user=user)
    out = StringIO()

    call_command("cart_reminders", stdout=out)

    assert "left@example.com" in out.getvalue()
    assert "1 cart(s) awaiting a reminder" in out.getvalue()
    assert mailoutbox == []  # the send lands with the email subsystem, not here

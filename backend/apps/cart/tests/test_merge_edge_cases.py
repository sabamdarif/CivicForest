"""Guest→user cart merge edge cases (plan.md §6) — beyond the happy path in test_cart."""

from __future__ import annotations

import pytest

from apps.cart import services
from apps.cart.models import Cart, CartItem
from apps.common.factories import (
    CartFactory,
    CartItemFactory,
    CouponFactory,
    GuestCartFactory,
    ProductVariantFactory,
    UserFactory,
)

pytestmark = pytest.mark.django_db


def test_merge_no_guest_cart_is_a_noop():
    user = UserFactory()
    services.merge_guest_cart_into_user("no-such-session", user)
    services.merge_guest_cart_into_user("", user)
    assert not Cart.objects.filter(user=user).exists()  # no cart conjured from nothing


def test_merge_creates_user_cart_when_none_exists():
    guest = GuestCartFactory()
    item = CartItemFactory(cart=guest, quantity=2)
    user = UserFactory()

    services.merge_guest_cart_into_user(guest.session_key, user)

    user_cart = Cart.objects.get(user=user)
    assert user_cart.items.get(variant=item.variant).quantity == 2
    assert not Cart.objects.filter(pk=guest.pk).exists()


def test_merge_drops_out_of_stock_lines():
    variant = ProductVariantFactory(stock_quantity=0)
    guest = GuestCartFactory()
    CartItem.objects.create(cart=guest, variant=variant, quantity=1)
    user = UserFactory()

    services.merge_guest_cart_into_user(guest.session_key, user)

    user_cart = Cart.objects.get(user=user)
    assert user_cart.items.count() == 0


def test_merge_coupon_carries_over_only_if_user_cart_has_none():
    coupon_guest = CouponFactory(code="GUEST10")
    coupon_user = CouponFactory(code="USER20")

    # User cart already has a coupon → guest's is dropped.
    guest = GuestCartFactory(coupon=coupon_guest)
    user = UserFactory()
    user_cart = CartFactory(user=user, coupon=coupon_user)
    services.merge_guest_cart_into_user(guest.session_key, user)
    user_cart.refresh_from_db()
    assert user_cart.coupon == coupon_user

    # User cart has no coupon → guest's carries over.
    guest2 = GuestCartFactory(coupon=coupon_guest)
    user2 = UserFactory()
    services.merge_guest_cart_into_user(guest2.session_key, user2)
    assert Cart.objects.get(user=user2).coupon == coupon_guest


def test_merge_distinct_variants_both_survive():
    guest = GuestCartFactory()
    a = CartItemFactory(cart=guest, quantity=1)
    user = UserFactory()
    user_cart = CartFactory(user=user)
    b = CartItemFactory(cart=user_cart, quantity=2)

    services.merge_guest_cart_into_user(guest.session_key, user)

    assert user_cart.items.count() == 2
    assert user_cart.items.get(variant=a.variant).quantity == 1
    assert user_cart.items.get(variant=b.variant).quantity == 2


def test_merge_is_idempotent_second_call_noop():
    guest = GuestCartFactory()
    item = CartItemFactory(cart=guest, quantity=2)
    user = UserFactory()

    services.merge_guest_cart_into_user(guest.session_key, user)
    services.merge_guest_cart_into_user(guest.session_key, user)  # guest gone → no-op

    assert Cart.objects.get(user=user).items.get(variant=item.variant).quantity == 2

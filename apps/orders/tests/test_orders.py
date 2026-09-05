from decimal import Decimal

import pytest

from apps.cart.models import Cart, CartItem, Coupon, CouponRedemption
from apps.orders import services
from apps.orders.models import Order

from .conftest import SHIPPING

pytestmark = pytest.mark.django_db


def _cart_with(user, variant, qty):
    cart = Cart.objects.create(user=user)
    CartItem.objects.create(cart=cart, variant=variant, quantity=qty)
    return cart


# ─── create_order_from_cart snapshots totals ─────────────────────────────────
def test_create_order_snapshots_totals(user, variant):
    cart = _cart_with(user, variant, 2)
    order = services.create_order_from_cart(user, cart, SHIPPING)

    assert order.status == Order.Status.PAYMENT_PENDING
    assert order.subtotal == Decimal("1600.00")
    assert order.total == Decimal("1600.00")  # over free-shipping threshold
    assert order.items.count() == 1
    item = order.items.get()
    assert item.unit_price == Decimal("800.00")
    assert item.quantity == 2
    assert item.variant_sku == "CBT-BLACK-M"


def test_order_number_is_non_sequential_and_prefixed(user, variant):
    o1 = services.create_order_from_cart(user, _cart_with(user, variant, 1), SHIPPING)
    assert o1.order_number.startswith("CF-")
    assert len(o1.order_number) == 11


def test_empty_cart_cannot_checkout(user):
    cart = Cart.objects.create(user=user)
    with pytest.raises(services.OrderError) as exc:
        services.create_order_from_cart(user, cart, SHIPPING)
    assert exc.value.code == "empty_cart"


def test_checkout_links_pending_custom_designs(user, variant, settings, tmp_path):
    """A pending custom design for a variant in the cart attaches to the new order, so
    the payment webhook can submit it to Qikink for direct dropship delivery."""
    from django.core.files.base import ContentFile

    from apps.custom_orders.models import CustomDesignOrder

    settings.MEDIA_ROOT = str(tmp_path)
    custom = CustomDesignOrder(user=user, variant=variant)
    custom.design_file.save("art.png", ContentFile(b"fake-png"), save=True)

    order = services.create_order_from_cart(user, _cart_with(user, variant, 1), SHIPPING)

    custom.refresh_from_db()
    assert custom.order_id == order.id
    assert order.has_custom_items is True
    assert order.items.get().is_custom is True


# ─── State machine ───────────────────────────────────────────────────────────
def test_legal_transition_advances_status(user, variant):
    order = services.create_order_from_cart(user, _cart_with(user, variant, 1), SHIPPING)
    order = services.transition(order, Order.Status.PAID)
    order = services.transition(order, Order.Status.PROCESSING)
    order = services.transition(order, Order.Status.SHIPPED)
    assert order.status == Order.Status.SHIPPED


def test_illegal_transition_is_rejected(user, variant):
    order = services.create_order_from_cart(user, _cart_with(user, variant, 1), SHIPPING)
    # Cannot ship an order that hasn't been paid.
    with pytest.raises(services.OrderError) as exc:
        services.transition(order, Order.Status.SHIPPED)
    assert exc.value.code == "illegal_transition"


def test_transition_is_idempotent_to_same_state(user, variant):
    order = services.create_order_from_cart(user, _cart_with(user, variant, 1), SHIPPING)
    services.transition(order, Order.Status.PAYMENT_PENDING)  # no-op, no raise
    assert order.status == Order.Status.PAYMENT_PENDING


# ─── Stock reservation (row-lock guard) ──────────────────────────────────────
def test_two_orders_for_last_unit_only_one_reserves(user, other_user, variant):
    variant.stock_quantity = 1
    variant.save()
    order_a = services.create_order_from_cart(user, _cart_with(user, variant, 1), SHIPPING)
    order_b = services.create_order_from_cart(
        other_user, _cart_with(other_user, variant, 1), SHIPPING
    )

    services.reserve_stock(order_a)  # succeeds, stock → 0
    variant.refresh_from_db()
    assert variant.stock_quantity == 0

    with pytest.raises(services.InsufficientStock):
        services.reserve_stock(order_b)  # nothing left


def test_reserve_stock_is_all_or_nothing(user, variant):
    variant.stock_quantity = 5
    variant.save()
    order = services.create_order_from_cart(user, _cart_with(user, variant, 2), SHIPPING)
    services.reserve_stock(order)
    variant.refresh_from_db()
    assert variant.stock_quantity == 3


def test_fulfilment_keeps_same_variant_readded_after_checkout(user, variant):
    cart = _cart_with(user, variant, 1)
    original = cart.items.get()
    order = services.create_order_from_cart(user, cart, SHIPPING)
    original.delete()
    replacement = CartItem.objects.create(cart=cart, variant=variant, quantity=1)

    services.fulfil_paid_order(order, cart=cart)

    assert cart.items.filter(id=replacement.id).exists()


# ─── Coupon usage is counted by the paid order, not the applied coupon ────────
def _paid_with_coupon(user, variant, **coupon_kwargs):
    coupon = Coupon.objects.create(
        code="SAVE10", discount_type="percent", value=Decimal("10"), **coupon_kwargs
    )
    cart = _cart_with(user, variant, 1)
    cart.coupon = coupon
    cart.save(update_fields=["coupon"])
    order = services.create_order_from_cart(user, cart, SHIPPING)
    assert order.coupon_code == "SAVE10"
    return coupon, order


def test_a_paid_order_counts_against_the_coupon_and_the_customer(user, variant):
    coupon, order = _paid_with_coupon(user, variant)

    services.fulfil_paid_order(order)

    coupon.refresh_from_db()
    assert coupon.used_count == 1
    redemption = CouponRedemption.objects.get(coupon=coupon, order=order)
    assert redemption.user_id == user.id


def test_counting_the_same_order_twice_records_one_use(user, variant):
    """The `is_paid` guard stops a replayed webhook, and the unique constraint stops anything
    that gets past it."""
    coupon, order = _paid_with_coupon(user, variant)

    services.fulfil_paid_order(order)
    services._record_coupon_use(order)

    assert CouponRedemption.objects.filter(coupon=coupon, order=order).count() == 1


def test_a_coupon_already_at_its_cap_still_records_the_use_it_was_paid_for(user, variant):
    # Money is captured by the time this runs, so the redemption is recorded either way and
    # the overrun is a log line for staff rather than a lost order.
    coupon, order = _paid_with_coupon(user, variant, max_uses=1)
    Coupon.objects.filter(pk=coupon.pk).update(used_count=1)

    services.fulfil_paid_order(order)

    coupon.refresh_from_db()
    assert coupon.used_count == 1  # the conditional increment refused to go past the cap
    assert CouponRedemption.objects.filter(coupon=coupon, order=order).exists()

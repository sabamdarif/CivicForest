"""Order services: creation from a cart, the status state machine, and stock reservation.

All order state lives behind these functions. Views/webhooks orchestrate; they never
mutate ``Order.status`` or stock directly. The state machine rejects illegal jumps
(e.g. shipping an unpaid order) so a bug or a replayed webhook can't corrupt state."""

from __future__ import annotations

import logging

from django.db import transaction
from django.db.models import F, Q
from django.utils import timezone

from apps.cart import services as cart_services
from apps.catalog.models import ProductVariant

from .models import Order, OrderItem, Shipment, StatusEvent

logger = logging.getLogger("orders")

# Legal forward transitions. Anything not listed raises (plan.md §4 order lifecycle).
_S = Order.Status
_ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    _S.CREATED: {_S.PAYMENT_PENDING, _S.CANCELLED},
    _S.PAYMENT_PENDING: {_S.PAID, _S.CANCELLED},
    _S.PAID: {_S.PROCESSING, _S.PARTIALLY_SHIPPED, _S.SHIPPED, _S.CANCELLED, _S.REFUNDED},
    _S.PROCESSING: {_S.PARTIALLY_SHIPPED, _S.SHIPPED, _S.CANCELLED, _S.REFUNDED},
    _S.PARTIALLY_SHIPPED: {_S.SHIPPED, _S.DELIVERED, _S.CANCELLED, _S.REFUNDED},
    _S.SHIPPED: {_S.PARTIALLY_SHIPPED, _S.DELIVERED, _S.REFUNDED},
    _S.DELIVERED: {_S.REFUNDED},
    _S.CANCELLED: set(),
    _S.REFUNDED: set(),
}


class OrderError(Exception):
    def __init__(self, message: str, code: str = "order_error"):
        super().__init__(message)
        self.message = message
        self.code = code


class InsufficientStock(OrderError):
    def __init__(self, message: str = "Insufficient stock to fulfil this order."):
        super().__init__(message, code="insufficient_stock")


@transaction.atomic
def transition(order: Order, to_status: str, *, actor=None, note: str = "") -> Order:
    """Move an order to ``to_status`` if the jump is legal, else raise. Idempotent when
    already in the target state. The row is re-read under lock so concurrent callers
    validate against the current database state rather than a stale model instance. Every
    real move writes a ``StatusEvent`` (the customer timeline and staff audit trail)."""
    order = Order.objects.select_for_update().get(pk=order.pk)
    if order.status == to_status:
        return order
    allowed = _ALLOWED_TRANSITIONS.get(order.status, set())
    if to_status not in allowed:
        raise OrderError(
            f"Cannot move order from {order.status} to {to_status}.",
            code="illegal_transition",
        )
    from_status = order.status
    order.status = to_status
    fields = ["status", "updated_at"]
    if to_status == Order.Status.CANCELLED:
        order.cancelled_at = timezone.now()
        order.cancel_reason = note[:200]
        fields += ["cancelled_at", "cancel_reason"]
    order.save(update_fields=fields)
    _log_event(order, from_status, to_status, actor, note)

    # Notify on the transitions the customer cares about. A send failure is swallowed
    # inside send_order_email, so a slow mail server cannot fail the caller.
    kind = {
        Order.Status.SHIPPED: "shipped",
        Order.Status.DELIVERED: "delivered",
        Order.Status.CANCELLED: "cancelled",
    }.get(to_status)
    if kind:
        from apps.common.email import send_order_email

        send_order_email(str(order.pk), kind)
    return order


def _log_event(order: Order, from_status: str, to_status: str, actor, note: str) -> None:
    StatusEvent.objects.create(
        order=order, from_status=from_status, to_status=to_status, actor=actor, note=note[:200]
    )


def recompute_order_status_from_shipments(order: Order, *, actor=None) -> Order:
    """Derive order status from its shipments (architecture §6): any shipped and any not →
    ``partially_shipped``; all shipped → ``shipped``; all delivered → ``delivered``. A no-op
    for an order with no shipments or one not yet past ``paid``, so it can never pull an order
    backwards out of a manual state. Writes a ``StatusEvent`` through ``transition``."""
    shipments = list(order.shipments.all())
    if not shipments or order.status not in {
        Order.Status.PAID,
        Order.Status.PROCESSING,
        Order.Status.PARTIALLY_SHIPPED,
        Order.Status.SHIPPED,
    }:
        return order

    if all(s.delivered_at for s in shipments):
        target = Order.Status.DELIVERED
    elif all(s.shipped_at for s in shipments):
        target = Order.Status.SHIPPED
    elif any(s.shipped_at for s in shipments):
        target = Order.Status.PARTIALLY_SHIPPED
    else:
        return order

    if target == order.status:
        return order
    return transition(order, target, actor=actor, note="derived from shipments")


@transaction.atomic
def create_order_from_cart(
    user, cart, shipping, *, checkout_key: str | None = None, rights_ack_text: str = ""
) -> Order:
    """Snapshot a priced cart into a new ``payment_pending`` order.

    ``shipping`` is a validated dict of address fields. ``rights_ack_text`` is the exact
    terms wording the customer ticked, stored as the consent record. The cart is left
    intact until payment is confirmed, so an abandoned payment doesn't lose the customer's
    cart: the cart is cleared in ``fulfil_paid_order``."""
    priced = cart_services.price_cart(cart)
    if priced.item_count == 0:
        raise OrderError("Your cart is empty.", code="empty_cart")

    # Defensive re-check: nothing in the cart may exceed live stock at checkout time.
    for line in priced.lines:
        if line.quantity > line.variant.stock_quantity:
            raise InsufficientStock(
                f"Only {line.variant.stock_quantity} of {line.variant.product.name} left."
            )

    order = Order.objects.create(
        user=user,
        status=Order.Status.PAYMENT_PENDING,
        checkout_key=checkout_key,
        email=user.email,
        phone=shipping.get("phone", ""),
        ship_full_name=shipping["full_name"],
        ship_line1=shipping["line1"],
        ship_line2=shipping.get("line2", ""),
        ship_city=shipping["city"],
        ship_state=shipping["state"],
        ship_postal_code=shipping["postal_code"],
        ship_country=shipping.get("country", "IN"),
        currency=getattr(cart, "currency", "INR") or "INR",
        subtotal=priced.subtotal,
        discount=priced.discount,
        shipping_fee=priced.shipping,
        total=priced.total,
        coupon_code=priced.coupon_code or "",
        rights_ack_text=rights_ack_text,
    )
    OrderItem.objects.bulk_create(
        [
            OrderItem(
                order=order,
                cart_item_id=line.cart_item_id,
                variant=line.variant,
                product_name=line.variant.product.name,
                variant_sku=line.variant.sku,
                size=line.variant.size,
                color=line.variant.color,
                unit_price=line.unit_price,
                quantity=line.quantity,
                line_total=line.line_total,
            )
            for line in priced.lines
        ]
    )
    _attach_custom_designs(user, order, [line.variant.id for line in priced.lines])
    return order


def _attach_custom_designs(user, order: Order, variant_ids: list) -> None:
    """Link the user's pending custom designs for these variants to the new order. This
    is what lets the payment webhook submit them to Qikink, which dropships straight to
    the order's shipping address (qikink_shipping=1)."""
    try:
        from apps.custom_orders.models import CustomDesignOrder
    except ImportError:  # custom_orders app optional
        return

    linked = CustomDesignOrder.objects.filter(
        user=user,
        order__isnull=True,
        submit_status=CustomDesignOrder.SubmitStatus.PENDING_PAYMENT,
        variant_id__in=variant_ids,
    ).update(order=order)
    if not linked:
        return

    order.items.filter(variant_id__in=order.custom_designs.values("variant_id")).update(
        is_custom=True
    )
    # mixed if any stock line remains alongside the custom ones, else all-custom.
    has_stock = order.items.filter(is_custom=False).exists()
    order.has_custom_items = True
    order.fulfilment_kind = Order.Fulfilment.MIXED if has_stock else Order.Fulfilment.CUSTOM
    order.save(update_fields=["has_custom_items", "fulfilment_kind", "updated_at"])


@transaction.atomic
def reserve_stock(order: Order) -> None:
    """Atomically decrement stock for every line, locking the variant rows first.

    On Postgres ``select_for_update`` serialises two concurrent confirmations against
    the same last unit, so exactly one succeeds; the other raises ``InsufficientStock``.
    All-or-nothing: if any line can't be satisfied, the transaction rolls back and no
    stock is touched."""
    items = list(order.items.select_related("variant"))
    variant_ids = [i.variant_id for i in items if i.variant_id]
    locked = {
        v.id: v for v in ProductVariant.objects.select_for_update().filter(id__in=variant_ids)
    }
    for item in items:
        if not item.variant_id:
            continue
        variant = locked.get(item.variant_id)
        if variant is None or variant.stock_quantity < item.quantity:
            raise InsufficientStock(
                f"Only {getattr(variant, 'stock_quantity', 0)} of {item.product_name} left."
            )
    for item in items:
        variant = locked.get(item.variant_id) if item.variant_id else None
        if variant is not None:
            variant.stock_quantity -= item.quantity
            variant.save(update_fields=["stock_quantity", "updated_at"])


@transaction.atomic
def fulfil_paid_order(order: Order, cart=None) -> Order | None:
    """Called once, from the verified payment webhook. Reserves stock under row locks,
    marks the order paid, records the coupon use, and clears the customer's cart.

    Returns the paid order only when this call performed the transition. A replayed
    webhook that finds the order already paid returns ``None`` without side effects."""
    order = Order.objects.select_for_update().get(pk=order.pk)
    if order.is_paid:
        return None

    reserve_stock(order)
    order.status = Order.Status.PAID
    order.save(update_fields=["status", "updated_at"])
    _log_event(order, Order.Status.PAYMENT_PENDING, Order.Status.PAID, None, "payment verified")
    _create_shipments(order)

    if order.coupon_code:
        _record_coupon_use(order)

    if cart is not None:
        # Delete only the lines this order snapshotted: anything the customer added
        # after checkout stays in the cart.
        ordered_cart_item_ids = [i.cart_item_id for i in order.items.all() if i.cart_item_id]
        cart.items.filter(id__in=ordered_cart_item_ids).delete()
        cart.coupon = None
        cart.save(update_fields=["coupon", "updated_at"])

    from apps.common.email import send_order_email

    send_order_email(str(order.pk), "confirmation")
    return order


def _create_shipments(order: Order) -> None:
    """Fan a paid order out into shipments: one for its stock lines (CivicForest packs and
    ships) and one for its custom lines (Qikink prints and dropships). A stock-only order gets
    one stock shipment, a mixed order gets both (architecture §6). Idempotent via the unique
    (order, kind) constraint, so a second fulfilment attempt adds nothing."""
    items = list(order.items.all())
    by_kind = {
        Shipment.Kind.STOCK: [i for i in items if not i.is_custom],
        Shipment.Kind.CUSTOM: [i for i in items if i.is_custom],
    }
    for kind, kind_items in by_kind.items():
        if not kind_items or order.shipments.filter(kind=kind).exists():
            continue
        shipment = Shipment.objects.create(order=order, kind=kind)
        shipment.items.set(kind_items)


def _record_coupon_use(order: Order) -> None:
    """Count a paid order against its coupon, globally and against the customer (J2).

    A ``CouponRedemption`` row is the per-customer count, unique on coupon and order so a
    replayed webhook cannot claim a second use. The conditional increment closes the
    check-then-increment race on ``used_count``: N concurrent checkouts cannot collectively
    exceed ``max_uses``. Exceeding it is logged rather than raised, because the money is
    already captured by the time this runs.
    """
    from apps.cart.models import Coupon, CouponRedemption

    coupon = Coupon.objects.filter(code=order.coupon_code).first()
    if coupon is None:
        return

    claimed = Coupon.objects.filter(
        Q(max_uses__isnull=True) | Q(used_count__lt=F("max_uses")), pk=coupon.pk
    ).update(used_count=F("used_count") + 1)
    if not claimed:
        logger.warning(
            "Coupon %s exceeded max_uses on paid order %s", coupon.code, order.order_number
        )
    CouponRedemption.objects.get_or_create(
        coupon=coupon, order=order, defaults={"user_id": order.user_id}
    )

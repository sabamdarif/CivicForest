"""Cart & pricing services.

Everything that touches money, stock, or coupon validity lives here — never in a view
or serializer — so the same logic runs from the cart API, the checkout order-creation
path, and the login-merge signal without duplication (plan.md §3, §10).

``price_cart`` is the single source of truth for a cart's monetary total. The order
app calls it at checkout; the client is never trusted for any of these numbers.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from django.conf import settings
from django.db import transaction

from apps.catalog.models import ProductVariant

from .models import Cart, CartItem, Coupon

TWO_PLACES = Decimal("0.01")


class CartError(Exception):
    """Raised for client-correctable cart problems (out of stock, bad coupon).

    Carries a ``code`` so the API layer can map it onto the standard error envelope.
    """

    def __init__(self, message: str, code: str = "cart_error"):
        super().__init__(message)
        self.message = message
        self.code = code


def _shipping_flat() -> Decimal:
    return Decimal(str(getattr(settings, "SHIPPING_FLAT_RATE", "59.00")))


def _free_shipping_threshold() -> Decimal:
    return Decimal(str(getattr(settings, "FREE_SHIPPING_THRESHOLD", "999.00")))


# ─── Cart resolution ─────────────────────────────────────────────────────────
def get_or_create_cart(request) -> Cart:
    """Resolve the caller's cart: the user's cart when authenticated, otherwise a
    guest cart bound to the (server-issued) session key. Guest carts are never
    addressable by id, so one guest can't read another's."""
    if request.user.is_authenticated:
        cart, _ = Cart.objects.get_or_create(user=request.user)
        return cart

    if not request.session.session_key:
        request.session.save()
    session_key = request.session.session_key
    cart, _ = Cart.objects.get_or_create(user=None, session_key=session_key)
    return cart


def _active_variant(variant_id: str) -> ProductVariant:
    variant = (
        ProductVariant.objects.select_related("product")
        .filter(id=variant_id, is_active=True, product__is_active=True)
        .first()
    )
    if variant is None:
        raise CartError("That item is unavailable.", code="variant_unavailable")
    return variant


# ─── Mutations (stock re-checked every time) ─────────────────────────────────
def add_item(cart: Cart, variant_id: str, quantity: int) -> CartItem:
    if quantity < 1:
        raise CartError("Quantity must be at least 1.", code="invalid_quantity")
    variant = _active_variant(variant_id)

    item = cart.items.filter(variant=variant).first()
    current = item.quantity if item else 0
    desired = current + quantity
    if desired > variant.stock_quantity:
        raise CartError(f"Only {variant.stock_quantity} left in stock.", code="insufficient_stock")

    if item is None:
        item = CartItem.objects.create(cart=cart, variant=variant, quantity=desired)
    else:
        item.quantity = desired
        item.save(update_fields=["quantity", "updated_at"])
    return item


def set_item_quantity(cart: Cart, variant_id: str, quantity: int) -> CartItem | None:
    """Set an absolute quantity. Zero or less removes the line. Returns None if removed."""
    variant = _active_variant(variant_id)
    item = cart.items.filter(variant=variant).first()
    if item is None:
        raise CartError("That item is not in your cart.", code="item_not_found")

    if quantity < 1:
        item.delete()
        return None
    if quantity > variant.stock_quantity:
        raise CartError(f"Only {variant.stock_quantity} left in stock.", code="insufficient_stock")
    item.quantity = quantity
    item.save(update_fields=["quantity", "updated_at"])
    return item


def remove_item(cart: Cart, variant_id: str) -> None:
    cart.items.filter(variant_id=variant_id).delete()


# ─── Coupons ─────────────────────────────────────────────────────────────────
def apply_coupon(cart: Cart, code: str) -> Coupon:
    coupon = Coupon.objects.filter(code__iexact=(code or "").strip()).first()
    if coupon is None:
        raise CartError("That coupon code isn't valid.", code="coupon_invalid")

    subtotal = _subtotal(cart)
    ok, reason = coupon.validate_for(subtotal)
    if not ok:
        raise CartError(reason, code="coupon_invalid")

    cart.coupon = coupon
    cart.save(update_fields=["coupon", "updated_at"])
    return coupon


def remove_coupon(cart: Cart) -> None:
    if cart.coupon_id is not None:
        cart.coupon = None
        cart.save(update_fields=["coupon", "updated_at"])


# ─── Pricing (single source of truth) ────────────────────────────────────────
@dataclass
class PricedLine:
    variant: ProductVariant
    quantity: int
    unit_price: Decimal
    line_total: Decimal


@dataclass
class PricedCart:
    lines: list[PricedLine]
    subtotal: Decimal
    discount: Decimal
    shipping: Decimal
    total: Decimal
    coupon_code: str | None
    item_count: int


def _items_qs(cart: Cart):
    return cart.items.select_related("variant", "variant__product").all()


def _subtotal(cart: Cart) -> Decimal:
    total = Decimal("0")
    for item in _items_qs(cart):
        total += item.variant.effective_price * item.quantity
    return total.quantize(TWO_PLACES)


def price_cart(cart: Cart) -> PricedCart:
    """Recompute the full monetary breakdown from the database. Never trust a
    client-supplied total — this recomputation is what makes tampering pointless."""
    lines: list[PricedLine] = []
    subtotal = Decimal("0")
    item_count = 0
    for item in _items_qs(cart):
        unit = item.variant.effective_price
        line_total = (unit * item.quantity).quantize(TWO_PLACES)
        subtotal += line_total
        item_count += item.quantity
        lines.append(
            PricedLine(
                variant=item.variant,
                quantity=item.quantity,
                unit_price=unit.quantize(TWO_PLACES),
                line_total=line_total,
            )
        )
    subtotal = subtotal.quantize(TWO_PLACES)

    discount = Decimal("0.00")
    coupon_code = None
    if cart.coupon_id is not None:
        ok, _ = cart.coupon.validate_for(subtotal)
        if ok:
            discount = cart.coupon.discount_for(subtotal)
            coupon_code = cart.coupon.code
        # An invalid coupon (expired since applied, etc.) simply contributes no
        # discount rather than blocking the whole cart.

    discounted = subtotal - discount
    if item_count == 0:
        shipping = Decimal("0.00")
    elif discounted >= _free_shipping_threshold():
        shipping = Decimal("0.00")
    else:
        shipping = _shipping_flat().quantize(TWO_PLACES)

    total = (discounted + shipping).quantize(TWO_PLACES)
    return PricedCart(
        lines=lines,
        subtotal=subtotal,
        discount=discount,
        shipping=shipping,
        total=total,
        coupon_code=coupon_code,
        item_count=item_count,
    )


# ─── Login merge ─────────────────────────────────────────────────────────────
@transaction.atomic
def merge_guest_cart_into_user(session_key: str, user) -> None:
    """Fold a guest's session cart into their user cart on login. Quantities are summed
    but re-capped at live stock; a coupon carries over only if the user cart has none.
    The guest cart is then deleted."""
    if not session_key:
        return
    guest = (
        Cart.objects.filter(user__isnull=True, session_key=session_key)
        .prefetch_related("items__variant")
        .first()
    )
    if guest is None:
        return

    user_cart, _ = Cart.objects.get_or_create(user=user)
    for item in guest.items.all():
        existing = user_cart.items.filter(variant=item.variant).first()
        current = existing.quantity if existing else 0
        capped = min(current + item.quantity, item.variant.stock_quantity)
        if capped <= 0:
            continue
        if existing is None:
            CartItem.objects.create(cart=user_cart, variant=item.variant, quantity=capped)
        else:
            existing.quantity = capped
            existing.save(update_fields=["quantity", "updated_at"])

    if user_cart.coupon_id is None and guest.coupon_id is not None:
        user_cart.coupon_id = guest.coupon_id
        user_cart.save(update_fields=["coupon", "updated_at"])

    guest.delete()

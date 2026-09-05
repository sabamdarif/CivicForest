"""Cart & pricing services.

Everything that touches money, stock, or coupon validity lives here — never in a view
or serializer — so the same logic runs from the cart API, the checkout order-creation
path, and the login-merge signal without duplication (plan.md §3, §10).

``price_cart`` is the single source of truth for a cart's monetary total. The order
app calls it at checkout; the client is never trusted for any of these numbers.

Prices are tax-inclusive (C3), so GST is **extracted** from a line and never added to it:
a charge that first appears at checkout is drip pricing under the CCPA guidelines.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from django.conf import settings
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from apps.catalog.models import ProductVariant
from apps.catalog.services import price_display
from apps.common.formatting import rupees

from .models import Cart, CartItem, Coupon, CouponRedemption

TWO_PLACES = Decimal("0.01")
HUNDRED = Decimal("100")

# G7: ten of one item per order. Enforced here rather than in a view so the API, the form
# and the login merge cannot disagree about the ceiling.
MAX_LINE_QUANTITY = 10


class CartError(Exception):
    """Raised for client-correctable cart problems (out of stock, bad coupon).

    Carries a ``code`` so the API layer can map it onto the standard error envelope.
    """

    def __init__(self, message: str, code: str = "cart_error"):
        super().__init__(message)
        self.message = message
        self.code = code


def _shipping_flat() -> Decimal:
    return Decimal(str(settings.SHIPPING_FLAT_RATE))


def _free_shipping_threshold() -> Decimal:
    return Decimal(str(settings.FREE_SHIPPING_THRESHOLD))


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
    if desired > MAX_LINE_QUANTITY:
        raise CartError(
            f"You can order at most {MAX_LINE_QUANTITY} of one item.", code="max_quantity"
        )

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
    if quantity > MAX_LINE_QUANTITY:
        raise CartError(
            f"You can order at most {MAX_LINE_QUANTITY} of one item.", code="max_quantity"
        )
    item.quantity = quantity
    item.save(update_fields=["quantity", "updated_at"])
    return item


def remove_item(cart: Cart, variant_id: str) -> None:
    cart.items.filter(variant_id=variant_id).delete()


def clear(cart: Cart) -> None:
    """Empty the cart, coupon included: a coupon held against nothing is not a cart state."""
    cart.items.all().delete()
    remove_coupon(cart)


def revalidate(cart: Cart) -> list[str]:
    """Bring a cart back in line with live stock, returning one message per line changed (G9).

    Called on every cart view, before pricing, so a customer is never shown a total they
    cannot pay. It writes during a read deliberately: the alternative is quoting a price for
    a quantity that no longer exists, and it only writes when something has actually moved.
    """
    changed: list[str] = []
    for item in list(_items_qs(cart)):
        variant = item.variant
        name = f"{variant.product.name}, {variant.size} in {variant.color}"
        if not (variant.is_active and variant.product.is_active):
            item.delete()
            changed.append(f"{name} is no longer available, so we removed it from your cart.")
            continue
        available = min(variant.stock_quantity, MAX_LINE_QUANTITY)
        if item.quantity <= available:
            continue
        if available == 0:
            item.delete()
            changed.append(f"{name} has sold out, so we removed it from your cart.")
        else:
            item.quantity = available
            item.save(update_fields=["quantity", "updated_at"])
            changed.append(f"Only {available} of {name} left, so we reduced your quantity.")
    return changed


# ─── Coupons ─────────────────────────────────────────────────────────────────
def _has_paid_order(user_id) -> bool:
    # Deferred import: apps.orders imports this module.
    from apps.orders.models import Order

    return Order.objects.filter(user_id=user_id, status__in=Order.PAID_STATUSES).exists()


def _eligible_lines(coupon: Coupon, lines: list[PricedLine]) -> list[PricedLine]:
    """The lines a coupon covers (J2): its category and product scope, minus anything already
    discounted when it excludes sale items. A blank scope means the whole catalogue, and a
    scoped parent category covers its children (C8).

    "On sale" is whatever ``price_display`` calls a genuine discount, so a coupon and the Sale
    badge can never disagree about which lines those are.
    """
    categories = {category.id for category in coupon.scope_categories.all()}
    products = {product.id for product in coupon.scope_products.all()}
    eligible = []
    for line in lines:
        product = line.variant.product
        if categories or products:
            in_scope = product.id in products or product.category_id in categories
            if not in_scope and product.category.parent_id not in categories:
                continue
        if coupon.exclude_sale_items and price_display(product, line.variant)[1] is not None:
            continue
        eligible.append(line)
    return eligible


def check_coupon(coupon: Coupon, cart: Cart, subtotal: Decimal, lines: list[PricedLine]) -> str:
    """Why this coupon does not apply to this cart, or an empty string when it does.

    The per-user limit and the first-order rule need a customer, so a guest cart passes both
    here and meets them again at checkout, which decision 14 gates behind a login. The global
    ``used_count`` is likewise advisory: only the payment transaction that writes a
    ``CouponRedemption`` decides a use, exactly as C5 already treats the last unit of stock.
    """
    now = timezone.now()
    if not coupon.is_active:
        return "This coupon is no longer active."
    if coupon.starts_at is not None and coupon.starts_at > now:
        return "This coupon is not active yet."
    if coupon.expires_at is not None and coupon.expires_at < now:
        return "This coupon has expired."
    if coupon.max_uses is not None and coupon.used_count >= coupon.max_uses:
        return "This coupon has reached its usage limit."
    if subtotal < coupon.min_order_value:
        return f"Spend at least {rupees(coupon.min_order_value, 0)} to use this coupon."
    if cart.user_id:
        used = CouponRedemption.objects.filter(coupon=coupon, user_id=cart.user_id).count()
        if coupon.per_user_limit is not None and used >= coupon.per_user_limit:
            return "You have already used this coupon."
        if coupon.first_order_only and _has_paid_order(cart.user_id):
            return "This coupon is for a first order only."
    if not _eligible_lines(coupon, lines):
        return "This coupon does not apply to anything in your cart."
    return ""


def coupon_discount(coupon: Coupon, lines: list[PricedLine]) -> Decimal:
    """The amount off, taken on the lines the coupon covers rather than the whole cart."""
    covered = sum((line.line_total for line in _eligible_lines(coupon, lines)), Decimal("0"))
    return coupon.discount_for(covered)


def apply_coupon(cart: Cart, code: str) -> Coupon:
    coupon = Coupon.objects.filter(code__iexact=(code or "").strip()).first()
    if coupon is None:
        raise CartError("That coupon code isn't valid.", code="coupon_invalid")

    # Priced without the coupon attached, which is all the rules need: a subtotal and the lines.
    priced = price_cart(cart)
    reason = check_coupon(coupon, cart, priced.subtotal, priced.lines)
    if reason:
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
    cart_item_id: object
    variant: ProductVariant
    quantity: int
    unit_price: Decimal
    line_total: Decimal
    # Assigned in a second pass, once the cart-wide discount and shipping are known.
    tax_rate: Decimal = field(default_factory=lambda: Decimal("0.00"))
    tax: Decimal = field(default_factory=lambda: Decimal("0.00"))


@dataclass
class PricedCart:
    lines: list[PricedLine]
    subtotal: Decimal
    discount: Decimal
    shipping: Decimal
    tax: Decimal
    total: Decimal
    coupon_code: str | None
    item_count: int


def _items_qs(cart: Cart):
    return (
        cart.items.select_related("variant", "variant__product", "variant__product__category")
        .prefetch_related("variant__product__images")
        .all()
    )


def _apportion(amount: Decimal, weights: list[Decimal]) -> list[Decimal]:
    """Split an amount across lines pro rata by weight, the remainder on the last line.

    Splitting exactly is what lets the taxable values sum back to the total to the paise,
    which is the property a GST invoice has to satisfy (H8).
    """
    total = sum(weights, Decimal("0"))
    if not weights or total <= 0:
        return [Decimal("0.00") for _ in weights]
    shares = [(amount * weight / total).quantize(TWO_PLACES) for weight in weights]
    shares[-1] += amount - sum(shares, Decimal("0"))
    return shares


def _extract_tax(lines: list[PricedLine], discount: Decimal, shipping: Decimal) -> Decimal:
    """Set ``tax_rate`` and ``tax`` on every line and return the cart's GST total.

    The price already includes the tax (C3), so it is extracted: ``amount * r / (100 + r)``.
    The discount comes off the taxable value (CGST s.15(3)(a)) and freight follows the goods'
    rate, so both are apportioned across the lines before the rate is applied to each.
    """
    weights = [line.line_total for line in lines]
    less = _apportion(discount, weights)
    plus = _apportion(shipping, weights)
    tax = Decimal("0.00")
    for line, discounted, freight in zip(lines, less, plus, strict=True):
        rate = line.variant.product.tax_rate
        net = line.line_total - discounted + freight
        line.tax_rate = rate
        line.tax = (net * rate / (HUNDRED + rate)).quantize(TWO_PLACES)
        tax += line.tax
    return tax


def price_cart(cart: Cart) -> PricedCart:
    """Recompute the full monetary breakdown from the database. Never trust a
    client-supplied total: this recomputation is what makes tampering pointless."""
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
                cart_item_id=item.id,
                variant=item.variant,
                quantity=item.quantity,
                unit_price=unit.quantize(TWO_PLACES),
                line_total=line_total,
            )
        )
    subtotal = subtotal.quantize(TWO_PLACES)

    discount = Decimal("0.00")
    coupon_code = None
    free_shipping = False
    if cart.coupon_id is not None and not check_coupon(cart.coupon, cart, subtotal, lines):
        discount = coupon_discount(cart.coupon, lines)
        coupon_code = cart.coupon.code
        free_shipping = cart.coupon.free_shipping
        # A coupon that has become invalid since it was applied (expired, exhausted, or its
        # scope emptied out of the cart) contributes no discount rather than blocking the cart.

    discounted = subtotal - discount
    if item_count == 0 or free_shipping:
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
        tax=_extract_tax(lines, discount, shipping),
        total=total,
        coupon_code=coupon_code,
        item_count=item_count,
    )


# ─── What the header and the free-shipping bar print ─────────────────────────
def item_count(request) -> int:
    """Units in the caller's cart, for the header badge on every page.

    Zero without a query when the visitor has neither an account nor a session, which is most
    crawler and first-visit traffic. Tolerates a bare ``RequestFactory`` request, because the
    shell is rendered directly in template tests and on the styleguide.
    """
    user = getattr(request, "user", None)
    if user is not None and user.is_authenticated:
        where = {"cart__user": user}
    else:
        session = getattr(request, "session", None)
        key = session.session_key if session is not None else None
        if not key:
            return 0
        where = {"cart__user__isnull": True, "cart__session_key": key}
    return CartItem.objects.filter(**where).aggregate(units=Sum("quantity"))["units"] or 0


def shipping_progress(priced: PricedCart) -> dict | None:
    """What the free-shipping bar prints: the real shortfall, never a fabricated one (G2, J9).

    ``None`` for an empty cart, and a zero shortfall once the fee is already waived, whether
    the cart crossed the threshold or a coupon waived it.
    """
    threshold = _free_shipping_threshold()
    if priced.item_count == 0 or threshold <= 0:
        return None
    if priced.shipping == 0:
        return {"threshold": threshold, "shortfall": Decimal("0.00"), "percent": 100}
    reached = priced.subtotal - priced.discount
    return {
        "threshold": threshold,
        "shortfall": (threshold - reached).quantize(TWO_PLACES),
        "percent": min(int(reached / threshold * 100), 100),
    }


# ─── Login merge ─────────────────────────────────────────────────────────────
@transaction.atomic
def merge_guest_cart_into_user(session_key: str, user) -> None:
    """Fold a guest's session cart into their user cart on login. Quantities are summed
    but re-capped at live stock and at the ten-per-line ceiling; a coupon carries over only
    if the user cart has none. The guest cart is then deleted."""
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
        capped = min(current + item.quantity, item.variant.stock_quantity, MAX_LINE_QUANTITY)
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

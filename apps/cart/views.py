"""Cart and wishlist: the storefront's pages and forms, plus the internal JSON API.

Views stay thin: resolve the caller's cart, call a ``services`` function, and return the
freshly re-priced cart. Guest carts are allowed (session-bound); wishlist requires auth. A
``CartError`` from the service layer becomes a clean 400 in the standard envelope for the API
and a message on the page for a form. Neither path ever accepts a price from the client.

Every storefront mutation answers a plain post with a redirect and an ``X-Partial`` post with
the cart drawer, so one code path serves both the no-JavaScript baseline and ``cart.js``.
"""

from __future__ import annotations

import uuid

from django.contrib import messages
from django.http import Http404
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST
from rest_framework import status
from rest_framework.authentication import SessionAuthentication
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.catalog import services as catalog_services
from apps.catalog.models import Product
from apps.catalog.views import PARTIAL_HEADER

from . import services
from .models import Wishlist
from .serializers import (
    AddItemSerializer,
    ApplyCouponSerializer,
    CartSerializer,
    UpdateItemSerializer,
    WishlistItemSerializer,
    WishlistToggleSerializer,
)


class GuestCSRFSessionAuthentication(SessionAuthentication):
    """SessionAuthentication only CSRF-checks *authenticated* sessions; guest cart
    writes would otherwise accept cross-site POSTs."""

    def authenticate(self, request):
        result = super().authenticate(request)
        if result is None:
            self.enforce_csrf(request)
        return result


def _priced_response(request, cart, *, status_code=status.HTTP_200_OK) -> Response:
    priced = services.price_cart(cart)
    data = CartSerializer.for_cart(priced, context={"request": request})
    return Response(data, status=status_code)


def _error(exc: services.CartError) -> Response:
    return Response(
        {"error": {"code": exc.code, "message": exc.message, "details": {}}},
        status=status.HTTP_400_BAD_REQUEST,
    )


class CartView(APIView):
    """GET the current cart (guest or user), always freshly priced."""

    authentication_classes = [GuestCSRFSessionAuthentication]
    permission_classes = [AllowAny]

    def get(self, request):
        cart = services.get_or_create_cart(request)
        return _priced_response(request, cart)


class CartItemsView(APIView):
    """POST to add an item to the cart."""

    authentication_classes = [GuestCSRFSessionAuthentication]
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = AddItemSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        cart = services.get_or_create_cart(request)
        try:
            services.add_item(
                cart,
                str(serializer.validated_data["variant_id"]),
                serializer.validated_data["quantity"],
            )
        except services.CartError as exc:
            return _error(exc)
        return _priced_response(request, cart, status_code=status.HTTP_201_CREATED)


class CartItemDetailView(APIView):
    """PATCH to set an absolute quantity, DELETE to remove — keyed by variant id."""

    authentication_classes = [GuestCSRFSessionAuthentication]
    permission_classes = [AllowAny]

    def patch(self, request, variant_id):
        serializer = UpdateItemSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        cart = services.get_or_create_cart(request)
        try:
            services.set_item_quantity(cart, str(variant_id), serializer.validated_data["quantity"])
        except services.CartError as exc:
            return _error(exc)
        return _priced_response(request, cart)

    def delete(self, request, variant_id):
        cart = services.get_or_create_cart(request)
        services.remove_item(cart, str(variant_id))
        return _priced_response(request, cart)


class CartCouponView(APIView):
    """POST to apply a coupon code, DELETE to clear it."""

    authentication_classes = [GuestCSRFSessionAuthentication]
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = ApplyCouponSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        cart = services.get_or_create_cart(request)
        try:
            services.apply_coupon(cart, serializer.validated_data["code"])
        except services.CartError as exc:
            return _error(exc)
        return _priced_response(request, cart)

    def delete(self, request):
        cart = services.get_or_create_cart(request)
        services.remove_coupon(cart)
        return _priced_response(request, cart)


class WishlistView(APIView):
    """GET the user's wishlist; POST toggles a product in/out of it."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        items = (
            Wishlist.objects.filter(user=request.user)
            .select_related("product")
            .prefetch_related("product__images", "product__variants")
        )
        data = WishlistItemSerializer(items, many=True, context={"request": request}).data
        return Response({"results": data, "count": len(data)})

    def post(self, request):
        serializer = WishlistToggleSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        product = Product.objects.filter(
            id=serializer.validated_data["product_id"], is_active=True
        ).first()
        if product is None:
            return Response(
                {"error": {"code": "not_found", "message": "Product not found.", "details": {}}},
                status=status.HTTP_404_NOT_FOUND,
            )
        entry, created = Wishlist.objects.get_or_create(user=request.user, product=product)
        if not created:
            entry.delete()
        return Response({"product_id": str(product.id), "wishlisted": created})


class WishlistItemView(APIView):
    """DELETE a product from the wishlist by product id (idempotent)."""

    permission_classes = [IsAuthenticated]

    def delete(self, request, product_id):
        Wishlist.objects.filter(user=request.user, product_id=product_id).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


# ─── Storefront: the cart page, its forms and the drawer ─────────────────────
def cart_context(request) -> dict:
    """Everything the cart page and the drawer both print.

    Stock is revalidated before anything is priced (G9), so a total is never quoted for a
    quantity that has gone, and each repaired line says so in a message.
    """
    cart = services.get_or_create_cart(request)
    for note in services.revalidate(cart):
        messages.warning(request, note)
    priced = services.price_cart(cart)
    return {
        "priced": priced,
        "progress": services.shipping_progress(priced),
        "max_quantity": services.MAX_LINE_QUANTITY,
    }


def _cart_response(request, fallback: str = "/cart/"):
    """The drawer for a JavaScript caller, a redirect for a plain form post (P6).

    One code path serves both, so the page and the drawer can never disagree about a total, and
    the response to the action that opened the drawer *is* the drawer: no second request.
    """
    if request.headers.get(PARTIAL_HEADER):
        response = render(request, "cart/_drawer.html", cart_context(request))
    else:
        response = redirect(fallback)
    response["Vary"] = PARTIAL_HEADER
    return response


def _posted_variant(request) -> str:
    """A hand-edited form must not reach the ORM with a malformed id."""
    try:
        return str(uuid.UUID(request.POST.get("variant", "")))
    except ValueError:
        raise Http404 from None


def _target_quantity(request) -> int:
    """What the stepper is asking for: the number in the box, then the button's step.

    The value in the box is client input, so the service still caps it against live stock and
    G7's ten; zero or less removes the line.
    """
    try:
        quantity = int(request.POST.get("quantity", 1))
    except (TypeError, ValueError):
        quantity = 1
    op = request.POST.get("op", "")
    if op == "inc":
        return quantity + 1
    if op == "dec":
        return quantity - 1
    return quantity


def cart_page(request):
    """The cart page. A GET that may quietly repair the cart before pricing it, which is the
    point of G9: the page must not show a total the customer cannot pay."""
    context = cart_context(request)
    context["cross_sell"] = catalog_services.cross_sell(
        line.variant.product for line in context["priced"].lines
    )
    return render(request, "cart/page.html", context)


@require_POST
def cart_line(request):
    """One line's stepper, remove and move-to-wishlist controls, keyed by variant id.

    The submit button's ``op`` decides which, so a row is one form and every action works with
    no JavaScript (G4).
    """
    cart = services.get_or_create_cart(request)
    variant_id = _posted_variant(request)
    op = request.POST.get("op", "")
    if op == "wishlist":
        return _move_to_wishlist(request, cart, variant_id)
    try:
        if op == "remove":
            services.remove_item(cart, variant_id)
        else:
            services.set_item_quantity(cart, variant_id, _target_quantity(request))
    except services.CartError as exc:
        messages.error(request, exc.message)
    return _cart_response(request)


def _move_to_wishlist(request, cart, variant_id: str):
    """Save the line for later and take it out of the cart (G4).

    A guest is asked to sign in rather than sent to a login page that M5 has not mounted yet.
    Part 3 of the decision register defaults the heart to prompting login, and a message does
    that without costing the customer their place on the page.
    """
    if not request.user.is_authenticated:
        messages.info(request, "Sign in to save items to your wishlist.")
        return _cart_response(request)

    item = cart.items.select_related("variant__product").filter(variant_id=variant_id).first()
    if item is None:
        messages.error(request, "That item is not in your cart.")
        return _cart_response(request)

    Wishlist.objects.get_or_create(user=request.user, product_id=item.variant.product_id)
    services.remove_item(cart, variant_id)
    messages.success(request, f"{item.variant.product.name} is saved to your wishlist.")
    return _cart_response(request)


@require_POST
def cart_clear(request):
    services.clear(services.get_or_create_cart(request))
    messages.success(request, "Your cart is empty again.")
    return _cart_response(request)


@require_POST
def cart_coupon(request):
    """Apply a code or drop the one that is applied (G3). The client sends a code and never an
    amount, so the discount on the summary is always the server's own arithmetic."""
    cart = services.get_or_create_cart(request)
    if request.POST.get("op") == "remove":
        services.remove_coupon(cart)
        messages.success(request, "Coupon removed.")
        return _cart_response(request)

    try:
        coupon = services.apply_coupon(cart, request.POST.get("code", ""))
    except services.CartError as exc:
        messages.error(request, exc.message)
    else:
        messages.success(request, f"{coupon.code} applied.")
    return _cart_response(request)


# ─── Storefront: the form the product page posts ─────────────────────────────
@require_POST
def add_to_cart(request):
    """Add to cart without JavaScript (P6): a form posts, the server decides, the customer
    lands back on the product page with a message.

    The client sends a product slug plus the size and colour it displayed, never a variant id
    and never a price. Resolving the variant here is what stops a swapped id reaching a
    different product, and `services.add_item` re-checks stock on the way in.
    """
    slug = request.POST.get("product", "")
    product = Product.objects.filter(slug=slug, is_active=True).first()
    if product is None:
        raise Http404

    quantity = _clamp_quantity(request.POST.get("quantity"))
    variant = (
        product.variants.filter(
            is_active=True,
            size__iexact=request.POST.get("size", ""),
            color__iexact=request.POST.get("color", ""),
        )
        .order_by("created_at")
        .first()
    )

    if variant is None:
        messages.error(request, "Choose a size and colour that is available.")
    else:
        try:
            services.add_item(services.get_or_create_cart(request), str(variant.id), quantity)
        except services.CartError as exc:
            messages.error(request, exc.message)
        else:
            messages.success(
                request, f"{product.name}, {variant.size} in {variant.color}, is in your cart."
            )
    return _cart_response(request, product.get_absolute_url())


def _clamp_quantity(raw) -> int:
    """A hand-edited form widens to the allowed range rather than failing (G7 caps a line at
    ten). The service enforces the same ceiling for anything that does not come through here."""
    try:
        quantity = int(raw)
    except (TypeError, ValueError):
        return 1
    return max(1, min(quantity, services.MAX_LINE_QUANTITY))

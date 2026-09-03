"""Cart and wishlist: the internal JSON API, plus the storefront's add-to-cart form.

Views stay thin: resolve the caller's cart, call a ``services`` function, and return the
freshly re-priced cart. Guest carts are allowed (session-bound); wishlist requires auth. A
``CartError`` from the service layer becomes a clean 400 in the standard envelope for the API
and a message on the page for the form. Neither path ever accepts a price from the client.
"""

from __future__ import annotations

from django.contrib import messages
from django.http import Http404
from django.shortcuts import redirect
from django.views.decorators.http import require_POST
from rest_framework import status
from rest_framework.authentication import SessionAuthentication
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.catalog.models import Product

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

# G7: ten per line. The stepper macro already defaults to this maximum.
MAX_LINE_QUANTITY = 10


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
    return redirect(product.get_absolute_url())


def _clamp_quantity(raw) -> int:
    """A hand-edited form widens to the allowed range rather than failing (G7 caps a line at
    ten). M4 task 1 moves the cap into the service, where the cart page needs it too."""
    try:
        quantity = int(raw)
    except (TypeError, ValueError):
        return 1
    return max(1, min(quantity, MAX_LINE_QUANTITY))

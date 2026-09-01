"""Cart & wishlist API.

Views stay thin: resolve the caller's cart, call a ``services`` function, and return
the freshly re-priced cart. Guest carts are allowed (session-bound); wishlist requires
auth. A ``CartError`` from the service layer becomes a clean 400 in the standard
envelope."""

from __future__ import annotations

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


class GuestCSRFSessionAuthentication(SessionAuthentication):
    """SessionAuthentication only CSRF-checks *authenticated* sessions; guest cart
    writes would otherwise accept cross-site POSTs (bugs.md #11)."""

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

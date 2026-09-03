"""The cart's internal JSON routes, mounted under /api/v1/ (A13).

The storefront's own routes are in `urls.py`, the same split `apps/catalog` uses.
"""

from django.urls import path

from .views import (
    CartCouponView,
    CartItemDetailView,
    CartItemsView,
    CartView,
    WishlistItemView,
    WishlistView,
)

# Slash-optional, matching the rest of the API and the typed frontend client.
urlpatterns = [
    path("cart", CartView.as_view(), name="cart"),
    path("cart/items", CartItemsView.as_view(), name="cart-items"),
    path("cart/items/<uuid:variant_id>", CartItemDetailView.as_view(), name="cart-item-detail"),
    path("cart/coupon", CartCouponView.as_view(), name="cart-coupon"),
    path("wishlist", WishlistView.as_view(), name="wishlist"),
    path("wishlist/<uuid:product_id>", WishlistItemView.as_view(), name="wishlist-item"),
]

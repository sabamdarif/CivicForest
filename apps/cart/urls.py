"""The cart's storefront routes, mounted at the root.

The cart page, the form target the product page posts to, one route per cart action, and the
wishlist, which lives here because `apps/cart` owns the `Wishlist` model.

Each cart action answers a plain post with a redirect and an ``X-Partial`` post with the drawer,
so the same URLs serve the no-JavaScript baseline and ``cart.js``.

The names are distinct from the JSON routes in `api_urls.py`, which already own `cart`,
`cart-coupon`, `wishlist` and `wishlist-item`: two patterns sharing a name would make `url()`
return whichever loaded last.
"""

from django.urls import path

from . import views

urlpatterns = [
    path("cart/", views.cart_page, name="cart-page"),
    path("cart/add/", views.add_to_cart, name="cart-add"),
    path("cart/line/", views.cart_line, name="cart-line"),
    path("cart/clear/", views.cart_clear, name="cart-clear"),
    path("cart/coupon/", views.cart_coupon, name="cart-apply-coupon"),
    path("account/wishlist/", views.wishlist, name="wishlist-page"),
]

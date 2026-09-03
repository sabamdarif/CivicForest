"""The cart's storefront routes, mounted at the root.

Just the add-to-cart form target for now. The cart page and its drawer are M4's; until then
`/cart/` 404s exactly as the header's cart link already does.
"""

from django.urls import path

from . import views

urlpatterns = [
    path("cart/add/", views.add_to_cart, name="cart-add"),
]

"""The orders app's storefront routes, mounted at the root.

`/checkout/` is here rather than in a checkout app because `apps/orders` owns the Order the page
creates. The JSON routes are in `api_urls.py`, and the names are distinct from theirs: `checkout`
already belongs to the JSON endpoint.
"""

from django.urls import path

from . import views

urlpatterns = [
    path("checkout/", views.checkout_page, name="checkout-page"),
    path("checkout/pay/<str:order_number>/", views.checkout_pay, name="checkout-pay"),
    path(
        "checkout/thank-you/<str:order_number>/",
        views.checkout_thank_you,
        name="checkout-thank-you",
    ),
    path("account/orders/", views.account_orders, name="account-orders"),
    path(
        "account/orders/<str:order_number>/",
        views.account_order_detail,
        name="account-order-detail",
    ),
]

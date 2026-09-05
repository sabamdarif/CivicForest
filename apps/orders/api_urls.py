"""The internal JSON routes for orders and checkout, mounted under /api/v1/.

The storefront's own routes are in `urls.py`, the same split `apps/cart` and `apps/search` use.
"""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import CheckoutView, OrderViewSet

router = DefaultRouter(trailing_slash=False)
router.register("orders", OrderViewSet, basename="order")

urlpatterns = [
    path("checkout", CheckoutView.as_view(), name="checkout"),
    path("", include(router.urls)),
]

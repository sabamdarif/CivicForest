from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import AddressViewSet, CurrentUserView

router = DefaultRouter(trailing_slash=False)
router.register("account/addresses", AddressViewSet, basename="address")

urlpatterns = [
    path("account/me", CurrentUserView.as_view(), name="current-user"),
    path("", include(router.urls)),
]

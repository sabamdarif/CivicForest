from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import CustomDesignViewSet

router = DefaultRouter(trailing_slash=False)
router.register("custom-designs", CustomDesignViewSet, basename="custom-design")

urlpatterns = [path("", include(router.urls))]

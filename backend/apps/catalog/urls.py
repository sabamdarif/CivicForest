from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import CategoryViewSet, FacetsView, ProductViewSet

# Slash-optional JSON API: URLs have no trailing slash, matching the typed frontend
# client. Avoids 301 redirects on every catalog request.
router = DefaultRouter(trailing_slash=False)
router.register("catalog/categories", CategoryViewSet, basename="category")
router.register("catalog/products", ProductViewSet, basename="product")

urlpatterns = [
    path("catalog/facets", FacetsView.as_view(), name="catalog-facets"),
    path("", include(router.urls)),
]

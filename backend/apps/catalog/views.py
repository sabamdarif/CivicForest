from django.db.models import Count, Q
from rest_framework import mixins, viewsets
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from . import services
from .filters import ProductFilter
from .serializers import (
    CategorySerializer,
    ProductDetailSerializer,
    ProductListSerializer,
)


class CategoryViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    """Public, read-only list of active categories with product counts."""

    serializer_class = CategorySerializer
    permission_classes = [AllowAny]
    pagination_class = None

    def get_queryset(self):
        return services.active_categories().annotate(
            product_count=Count("products", filter=Q(products__is_active=True))
        )


class FacetsView(APIView):
    """Public filter options for the shop panel, built from live catalog data."""

    permission_classes = [AllowAny]

    def get(self, request):
        return Response(services.catalog_facets())


class ProductViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """Public, read-only catalog. List is filterable/sortable and paginated with a
    hard max page size; detail is looked up by slug."""

    permission_classes = [AllowAny]
    filterset_class = ProductFilter
    lookup_field = "slug"
    # "price" is the annotation from services.with_price — the price shown on the card.
    ordering_fields = ["created_at", "price", "name"]
    ordering = ["-created_at"]

    def get_queryset(self):
        products = services.active_products()
        return services.with_price(products) if self.action == "list" else products

    def get_serializer_class(self):
        if self.action == "retrieve":
            return ProductDetailSerializer
        return ProductListSerializer

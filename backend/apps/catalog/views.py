from django.db.models import Count, Q
from rest_framework import mixins, viewsets
from rest_framework.permissions import AllowAny

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


class ProductViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """Public, read-only catalog. List is filterable/sortable and paginated with a
    hard max page size; detail is looked up by slug."""

    permission_classes = [AllowAny]
    filterset_class = ProductFilter
    lookup_field = "slug"
    ordering_fields = ["created_at", "base_price", "name"]
    ordering = ["-created_at"]

    def get_queryset(self):
        return services.active_products()

    def get_serializer_class(self):
        if self.action == "retrieve":
            return ProductDetailSerializer
        return ProductListSerializer

import django_filters as filters
from django.db.models import Q

from .models import Product


class ProductFilter(filters.FilterSet):
    """Storefront shop filters: category, size, color, price range, material.

    Size/color match against the product's variants so a product shows up if *any*
    active variant qualifies. Maps directly onto the filter panel in the mockups.
    """

    category = filters.CharFilter(field_name="category__slug", lookup_expr="iexact")
    material = filters.CharFilter(field_name="material__slug", lookup_expr="iexact")
    size = filters.CharFilter(method="filter_size")
    color = filters.CharFilter(method="filter_color")
    min_price = filters.NumberFilter(field_name="base_price", lookup_expr="gte")
    max_price = filters.NumberFilter(field_name="base_price", lookup_expr="lte")
    is_new = filters.BooleanFilter(field_name="is_new")
    is_bestseller = filters.BooleanFilter(field_name="is_bestseller")

    class Meta:
        model = Product
        fields = ["category", "material", "size", "color", "is_new", "is_bestseller"]

    def filter_size(self, queryset, name, value):
        sizes = [s.strip() for s in value.split(",") if s.strip()]
        if not sizes:
            return queryset
        return queryset.filter(variants__size__in=sizes, variants__is_active=True).distinct()

    def filter_color(self, queryset, name, value):
        colors = [c.strip() for c in value.split(",") if c.strip()]
        if not colors:
            return queryset
        q = Q()
        for color in colors:
            q |= Q(variants__color__iexact=color)
        return queryset.filter(q, variants__is_active=True).distinct()

import django_filters as filters
from django.db.models import Exists, OuterRef, Q

from . import services
from .models import Product, ProductVariant


def _csv(value: str | None) -> list[str]:
    return [item.strip() for item in (value or "").split(",") if item.strip()]


def _any_iexact(field: str, values: list[str]) -> Q:
    """OR of case-insensitive matches — a URL typed as ``size=m`` must still
    match the ``M`` stored on the variant."""
    query = Q()
    for value in values:
        query |= Q(**{f"{field}__iexact": value})
    return query


class ProductFilter(filters.FilterSet):
    """Storefront shop filters: category, size, price range, material."""

    category = filters.CharFilter(method="filter_category")
    material = filters.CharFilter(field_name="material__slug", lookup_expr="iexact")
    size = filters.CharFilter(method="filter_deferred")
    min_price = filters.NumberFilter(method="filter_price")
    max_price = filters.NumberFilter(method="filter_price")
    is_new = filters.BooleanFilter(field_name="is_new")
    is_bestseller = filters.BooleanFilter(field_name="is_bestseller")

    class Meta:
        model = Product
        fields = ["category", "material", "size", "is_new", "is_bestseller"]

    def filter_category(self, queryset, name, value):
        # Selecting a parent category includes its children (one level — that is all
        # the storefront nav exposes).
        # ponytail: one level of nesting; recurse via a CTE only if categories go deeper.
        return queryset.filter(
            Q(category__slug__iexact=value) | Q(category__parent__slug__iexact=value)
        )

    def filter_deferred(self, queryset, name, value):
        # size is handled in filter_queryset() against active variants.
        return queryset

    def filter_price(self, queryset, name, value):
        if "price" not in queryset.query.annotations:
            queryset = services.with_price(queryset)
        return queryset.filter(**{"price__gte" if name == "min_price" else "price__lte": value})

    def filter_queryset(self, queryset):
        queryset = super().filter_queryset(queryset)
        sizes = _csv(self.form.cleaned_data.get("size"))
        if not sizes:
            return queryset

        variant = Q(product=OuterRef("pk"), is_active=True)
        variant &= _any_iexact("size", sizes)
        # EXISTS instead of a join keeps one row per product — no distinct() needed,
        # so pagination counts stay correct.
        return queryset.filter(Exists(ProductVariant.objects.filter(variant)))

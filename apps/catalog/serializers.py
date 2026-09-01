from rest_framework import serializers

from .models import Category, Material, Product, ProductImage, ProductVariant

# All serializers here are read-only for the storefront. Every field is listed
# explicitly — never `fields = "__all__"` — and prices/stock are output-only so the
# client can never write them (plan.md §6).


class CategorySerializer(serializers.ModelSerializer):
    product_count = serializers.IntegerField(read_only=True, required=False)

    class Meta:
        model = Category
        fields = ["id", "name", "slug", "description", "display_order", "product_count"]


class MaterialSerializer(serializers.ModelSerializer):
    class Meta:
        model = Material
        fields = ["id", "name", "slug"]


class ProductImageSerializer(serializers.ModelSerializer):
    url = serializers.SerializerMethodField()

    class Meta:
        model = ProductImage
        fields = ["id", "url", "alt_text", "display_order"]

    def get_url(self, obj) -> str | None:
        request = self.context.get("request")
        if not obj.image:
            return None
        url = obj.image.url
        return request.build_absolute_uri(url) if request else url


class ProductVariantSerializer(serializers.ModelSerializer):
    price = serializers.DecimalField(
        source="effective_price", max_digits=10, decimal_places=2, read_only=True
    )
    in_stock = serializers.SerializerMethodField()

    class Meta:
        model = ProductVariant
        fields = ["id", "size", "color", "color_hex", "sku", "price", "in_stock"]

    def get_in_stock(self, obj) -> bool:
        return obj.is_active and obj.stock_quantity > 0


class ProductListSerializer(serializers.ModelSerializer):
    """Compact card payload for grids and rows."""

    category = serializers.CharField(source="category.name", read_only=True)
    category_slug = serializers.CharField(source="category.slug", read_only=True)
    price_from = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    thumbnail = serializers.SerializerMethodField()
    colors = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = [
            "id",
            "name",
            "slug",
            "category",
            "category_slug",
            "price_from",
            "is_new",
            "is_bestseller",
            "thumbnail",
            "colors",
        ]

    def get_thumbnail(self, obj) -> str | None:
        image = obj.images.all()[0] if obj.images.all() else None
        if not image:
            return None
        request = self.context.get("request")
        return request.build_absolute_uri(image.image.url) if request else image.image.url

    def get_colors(self, obj) -> list[dict]:
        seen: dict[str, str] = {}
        for v in obj.variants.all():
            if v.is_active and v.color not in seen:
                seen[v.color] = v.color_hex
        return [{"name": name, "hex": hex_} for name, hex_ in seen.items()]


class ProductDetailSerializer(ProductListSerializer):
    """Full detail payload for the product page."""

    material = serializers.CharField(source="material.name", read_only=True, default=None)
    images = ProductImageSerializer(many=True, read_only=True)
    variants = ProductVariantSerializer(many=True, read_only=True)
    sizes = serializers.SerializerMethodField()

    class Meta(ProductListSerializer.Meta):
        fields = ProductListSerializer.Meta.fields + [
            "description",
            "material",
            "base_price",
            "meta_title",
            "meta_description",
            "images",
            "variants",
            "sizes",
        ]

    def get_sizes(self, obj) -> list[str]:
        seen: list[str] = []
        for v in obj.variants.all():
            if v.is_active and v.size not in seen:
                seen.append(v.size)
        return seen

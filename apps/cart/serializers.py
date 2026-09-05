from __future__ import annotations

from rest_framework import serializers

from apps.catalog.models import Product

from .services import MAX_LINE_QUANTITY, PricedCart, PricedLine


class CartLineSerializer(serializers.Serializer):
    """A priced cart line. All monetary fields are server-computed and read-only —
    the client can only ever send a ``variant_id`` and a ``quantity`` (plan.md §10)."""

    variant_id = serializers.SerializerMethodField()
    product_name = serializers.SerializerMethodField()
    product_slug = serializers.SerializerMethodField()
    size = serializers.SerializerMethodField()
    color = serializers.SerializerMethodField()
    sku = serializers.SerializerMethodField()
    thumbnail = serializers.SerializerMethodField()
    unit_price = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    quantity = serializers.IntegerField(read_only=True)
    line_total = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    available_stock = serializers.SerializerMethodField()

    def get_variant_id(self, line: PricedLine) -> str:
        return str(line.variant.id)

    def get_product_name(self, line: PricedLine) -> str:
        return line.variant.product.name

    def get_product_slug(self, line: PricedLine) -> str:
        return line.variant.product.slug

    def get_size(self, line: PricedLine) -> str:
        return line.variant.size

    def get_color(self, line: PricedLine) -> str:
        return line.variant.color

    def get_sku(self, line: PricedLine) -> str:
        return line.variant.sku

    def get_available_stock(self, line: PricedLine) -> int:
        return line.variant.stock_quantity

    def get_thumbnail(self, line: PricedLine) -> str | None:
        product = line.variant.product
        images = list(product.images.all())
        if not images:
            return None
        request = self.context.get("request")
        url = images[0].image.url
        return request.build_absolute_uri(url) if request else url


class CartSerializer(serializers.Serializer):
    """Read view of a priced cart. ``tax`` is the GST already inside ``total``, never on top
    of it (C3), so a client that adds it to the total is wrong."""

    lines = CartLineSerializer(many=True, read_only=True)
    subtotal = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    discount = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    shipping = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    tax = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    total = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    coupon_code = serializers.CharField(read_only=True, allow_null=True)
    item_count = serializers.IntegerField(read_only=True)

    @classmethod
    def for_cart(cls, priced: PricedCart, *, context=None) -> dict:
        return cls(priced, context=context or {}).data


class AddItemSerializer(serializers.Serializer):
    variant_id = serializers.UUIDField()
    quantity = serializers.IntegerField(min_value=1, max_value=MAX_LINE_QUANTITY, default=1)


class UpdateItemSerializer(serializers.Serializer):
    # Zero is how a stepper removes a line, so it is valid input rather than an error.
    quantity = serializers.IntegerField(min_value=0, max_value=MAX_LINE_QUANTITY)


class ApplyCouponSerializer(serializers.Serializer):
    code = serializers.CharField(max_length=40)


class WishlistItemSerializer(serializers.Serializer):
    """Read shape for a wishlist entry — enough to render a product card."""

    id = serializers.SerializerMethodField()
    product_id = serializers.SerializerMethodField()
    name = serializers.SerializerMethodField()
    slug = serializers.SerializerMethodField()
    price_from = serializers.SerializerMethodField()
    thumbnail = serializers.SerializerMethodField()

    def _product(self, obj) -> Product:
        return obj.product

    def get_id(self, obj) -> str:
        return str(obj.id)

    def get_product_id(self, obj) -> str:
        return str(obj.product_id)

    def get_name(self, obj) -> str:
        return obj.product.name

    def get_slug(self, obj) -> str:
        return obj.product.slug

    def get_price_from(self, obj) -> str:
        return str(obj.product.price_from)

    def get_thumbnail(self, obj) -> str | None:
        images = list(obj.product.images.all())
        if not images:
            return None
        request = self.context.get("request")
        url = images[0].image.url
        return request.build_absolute_uri(url) if request else url


class WishlistToggleSerializer(serializers.Serializer):
    product_id = serializers.UUIDField()

from __future__ import annotations

from rest_framework import serializers

from .models import Order, OrderItem


class OrderItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderItem
        fields = [
            "id",
            "product_name",
            "variant_sku",
            "size",
            "color",
            "unit_price",
            "quantity",
            "line_total",
            "is_custom",
        ]


class OrderSerializer(serializers.ModelSerializer):
    """Read view of an order. Every monetary field is a server-owned snapshot; the
    client can never write status or totals."""

    items = OrderItemSerializer(many=True, read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = Order
        fields = [
            "order_number",
            "status",
            "status_display",
            "email",
            "phone",
            "ship_full_name",
            "ship_line1",
            "ship_line2",
            "ship_city",
            "ship_state",
            "ship_postal_code",
            "ship_country",
            "currency",
            "subtotal",
            "discount",
            "shipping_fee",
            "total",
            "coupon_code",
            "has_custom_items",
            "items",
            "created_at",
        ]
        read_only_fields = fields


class ShippingAddressSerializer(serializers.Serializer):
    """Inline shipping address supplied at checkout. Validated here; the order snapshots
    these values so later edits to a saved address don't rewrite historical orders."""

    full_name = serializers.CharField(max_length=120)
    phone = serializers.CharField(max_length=20)
    line1 = serializers.CharField(max_length=255)
    line2 = serializers.CharField(max_length=255, required=False, allow_blank=True)
    city = serializers.CharField(max_length=100)
    state = serializers.CharField(max_length=100)
    postal_code = serializers.CharField(max_length=16)
    country = serializers.CharField(max_length=2, required=False, default="IN")


class CheckoutSerializer(serializers.Serializer):
    """Checkout input: a shipping address, plus an optional flag to save it."""

    shipping_address = ShippingAddressSerializer()
    save_address = serializers.BooleanField(required=False, default=False)

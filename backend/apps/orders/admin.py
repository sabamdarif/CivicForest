from django.contrib import admin

from .models import Order, OrderItem


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    can_delete = False
    readonly_fields = [
        "product_name",
        "variant_sku",
        "size",
        "color",
        "unit_price",
        "quantity",
        "line_total",
        "is_custom",
    ]
    fields = readonly_fields

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ["order_number", "user", "status", "total", "currency", "created_at"]
    list_filter = ["status", "currency", "has_custom_items"]
    search_fields = ["order_number", "user__email", "ship_full_name"]
    date_hierarchy = "created_at"
    raw_id_fields = ["user"]
    inlines = [OrderItemInline]
    # Totals and the address snapshot are immutable history — never editable in admin.
    readonly_fields = [
        "order_number",
        "user",
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
        "created_at",
    ]

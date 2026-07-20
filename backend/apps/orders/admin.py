from django.contrib import admin, messages

from . import services
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
    actions = ["mark_processing", "mark_shipped", "mark_delivered", "mark_cancelled", "mark_refunded"]
    # Totals and the address snapshot are immutable history — never editable in admin.
    # ``status`` is read-only too: changes go through the actions below so the state
    # machine (and its emails) can't be bypassed with the raw dropdown (bugs.md #3).
    readonly_fields = [
        "status",
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

    def _transition(self, request, queryset, to_status):
        moved = 0
        for order in queryset:
            try:
                services.transition(order, to_status)
                moved += 1
            except services.OrderError as exc:
                self.message_user(request, f"{order.order_number}: {exc.message}", messages.ERROR)
        if moved:
            self.message_user(request, f"{moved} order(s) moved to {to_status}.", messages.SUCCESS)

    @admin.action(description="Mark processing")
    def mark_processing(self, request, queryset):
        self._transition(request, queryset, Order.Status.PROCESSING)

    @admin.action(description="Mark shipped")
    def mark_shipped(self, request, queryset):
        self._transition(request, queryset, Order.Status.SHIPPED)

    @admin.action(description="Mark delivered")
    def mark_delivered(self, request, queryset):
        self._transition(request, queryset, Order.Status.DELIVERED)

    @admin.action(description="Mark cancelled")
    def mark_cancelled(self, request, queryset):
        self._transition(request, queryset, Order.Status.CANCELLED)

    @admin.action(description="Mark refunded")
    def mark_refunded(self, request, queryset):
        self._transition(request, queryset, Order.Status.REFUNDED)

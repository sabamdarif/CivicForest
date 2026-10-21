from django.contrib import admin

from .models import Cart, CartItem, Coupon, CouponRedemption, Wishlist


class CartItemInline(admin.TabularInline):
    model = CartItem
    extra = 0
    autocomplete_fields = ["variant"]
    fields = ["variant", "quantity"]


class CouponRedemptionInline(admin.TabularInline):
    """Who has used the coupon. Read-only: a use is written by the payment transaction, and
    editing one here would let staff hand out or revoke uses without an order behind them."""

    model = CouponRedemption
    extra = 0
    can_delete = False
    fields = ["user", "order", "created_at"]
    readonly_fields = fields

    def has_add_permission(self, request, obj):
        return False


@admin.register(Coupon)
class CouponAdmin(admin.ModelAdmin):
    list_display = [
        "code",
        "discount_type",
        "value",
        "free_shipping",
        "min_order_value",
        "used_count",
        "max_uses",
        "per_user_limit",
        "starts_at",
        "expires_at",
        "is_active",
    ]
    list_editable = ["is_active"]
    list_filter = ["discount_type", "is_active", "free_shipping", "first_order_only"]
    search_fields = ["code"]
    readonly_fields = ["used_count"]
    autocomplete_fields = ["scope_categories", "scope_products"]
    inlines = [CouponRedemptionInline]
    fieldsets = [
        (None, {"fields": ["code", "is_active"]}),
        (
            "What it takes off",
            {
                "fields": ["discount_type", "value", "free_shipping"],
                "description": "Tick free shipping on its own for a shipping-only coupon, "
                "and leave the value at zero.",
            },
        ),
        (
            "Who and when",
            {
                "fields": [
                    "starts_at",
                    "expires_at",
                    "min_order_value",
                    "max_uses",
                    "per_user_limit",
                    "used_count",
                    "first_order_only",
                ],
                "description": "A blank limit means unlimited. The per-customer limit counts "
                "paid orders, so an abandoned cart never uses one up.",
            },
        ),
        (
            "What it applies to",
            {
                "fields": ["scope_categories", "scope_products", "exclude_sale_items"],
                "description": "Leave both lists empty for the whole catalogue. A category "
                "covers its child categories.",
            },
        ),
    ]


@admin.register(Cart)
class CartAdmin(admin.ModelAdmin):
    list_display = ["__str__", "user", "session_key", "coupon", "updated_at"]
    search_fields = ["user__email", "session_key"]
    raw_id_fields = ["user", "coupon"]
    inlines = [CartItemInline]


@admin.register(Wishlist)
class WishlistAdmin(admin.ModelAdmin):
    list_display = ["user", "product", "created_at"]
    search_fields = ["user__email", "product__name"]
    raw_id_fields = ["user", "product"]

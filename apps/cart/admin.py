from django.contrib import admin

from .models import Cart, CartItem, Coupon, Wishlist


class CartItemInline(admin.TabularInline):
    model = CartItem
    extra = 0
    autocomplete_fields = ["variant"]
    fields = ["variant", "quantity"]


@admin.register(Coupon)
class CouponAdmin(admin.ModelAdmin):
    list_display = [
        "code",
        "discount_type",
        "value",
        "min_order_value",
        "used_count",
        "max_uses",
        "expires_at",
        "is_active",
    ]
    list_editable = ["is_active"]
    list_filter = ["discount_type", "is_active"]
    search_fields = ["code"]
    readonly_fields = ["used_count"]


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

from django.contrib import admin

from .models import Category, Material, Product, ProductImage, ProductVariant, Tag


class ProductVariantInline(admin.TabularInline):
    model = ProductVariant
    extra = 1
    fields = ["size", "color", "color_hex", "sku", "price_override", "stock_quantity", "is_active"]


class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 1
    fields = ["image", "alt_text", "display_order", "variant"]


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ["name", "slug", "parent", "display_order", "is_active"]
    list_editable = ["display_order", "is_active"]
    list_filter = ["is_active"]
    prepopulated_fields = {"slug": ["name"]}
    search_fields = ["name"]


@admin.register(Material)
class MaterialAdmin(admin.ModelAdmin):
    list_display = ["name", "slug"]
    prepopulated_fields = {"slug": ["name"]}
    search_fields = ["name"]


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ["name", "slug"]
    prepopulated_fields = {"slug": ["name"]}
    search_fields = ["name"]


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = [
        "name",
        "category",
        "base_price",
        "is_new",
        "is_bestseller",
        "is_active",
    ]
    list_editable = ["is_new", "is_bestseller", "is_active"]
    list_filter = ["category", "material", "is_active", "is_new", "is_bestseller"]
    search_fields = ["name", "slug", "description"]
    prepopulated_fields = {"slug": ["name"]}
    autocomplete_fields = ["category", "material", "tags"]
    inlines = [ProductVariantInline, ProductImageInline]


@admin.register(ProductVariant)
class ProductVariantAdmin(admin.ModelAdmin):
    list_display = ["sku", "product", "size", "color", "stock_quantity", "is_active"]
    list_editable = ["stock_quantity", "is_active"]
    list_filter = ["size", "color", "is_active"]
    search_fields = ["sku", "product__name"]
    raw_id_fields = ["product"]

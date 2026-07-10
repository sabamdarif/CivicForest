from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import Address, User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    ordering = ["email"]
    list_display = ["email", "first_name", "last_name", "is_staff", "marketing_opt_in"]
    list_filter = ["is_staff", "is_superuser", "is_active", "marketing_opt_in"]
    search_fields = ["email", "first_name", "last_name"]
    # No username field on this model — override the parent's fieldsets.
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Personal info", {"fields": ("first_name", "last_name", "phone")}),
        ("Preferences", {"fields": ("marketing_opt_in",)}),
        (
            "Permissions",
            {
                "fields": (
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "groups",
                    "user_permissions",
                )
            },
        ),
        ("Important dates", {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("email", "password1", "password2"),
            },
        ),
    )


@admin.register(Address)
class AddressAdmin(admin.ModelAdmin):
    list_display = ["full_name", "user", "kind", "city", "state", "is_default"]
    list_filter = ["kind", "country", "is_default"]
    search_fields = ["full_name", "user__email", "city", "postal_code"]
    raw_id_fields = ["user"]

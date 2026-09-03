from django.contrib import admin

from .models import AnnouncementBar, HomeSection


@admin.register(AnnouncementBar)
class AnnouncementBarAdmin(admin.ModelAdmin):
    list_display = ["text", "is_active", "starts_at", "ends_at", "updated_at"]
    list_filter = ["is_active"]
    fields = ["text", "url", "is_active", "starts_at", "ends_at"]
    search_fields = ["text"]


@admin.register(HomeSection)
class HomeSectionAdmin(admin.ModelAdmin):
    """The five bands are seeded and there is one of each, so this is edit-only: adding a
    sixth or deleting one would leave the page with a kind the template cannot render."""

    list_display = ["kind", "title", "display_order", "is_active"]
    list_editable = ["display_order", "is_active"]
    list_display_links = ["kind"]
    fields = [
        "kind",
        "eyebrow",
        "title",
        "subtitle",
        "image",
        "target",
        "cta_label",
        "display_order",
        "is_active",
    ]
    readonly_fields = ["kind"]

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

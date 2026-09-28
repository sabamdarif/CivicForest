from django.contrib import admin

from .models import (
    AnnouncementBar,
    ContactMessage,
    FaqEntry,
    HomeSection,
    NewsletterSubscriber,
    Page,
)


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


@admin.register(Page)
class PageAdmin(admin.ModelAdmin):
    list_display = ["title", "slug", "is_published", "updated_at"]
    list_filter = ["is_published"]
    prepopulated_fields = {"slug": ["title"]}
    search_fields = ["title", "slug", "body"]


@admin.register(FaqEntry)
class FaqEntryAdmin(admin.ModelAdmin):
    list_display = ["question", "category", "display_order", "is_active"]
    list_editable = ["display_order", "is_active"]
    list_filter = ["is_active", "category"]
    search_fields = ["question", "answer"]


@admin.register(ContactMessage)
class ContactMessageAdmin(admin.ModelAdmin):
    list_display = ["subject", "email", "order_number", "handled_at", "created_at"]
    list_filter = ["handled_at"]
    search_fields = ["subject", "email", "message", "order_number"]
    readonly_fields = ["name", "email", "order_number", "subject", "message", "created_at"]


@admin.register(NewsletterSubscriber)
class NewsletterSubscriberAdmin(admin.ModelAdmin):
    list_display = ["email", "confirmed_at", "unsubscribed_at", "source", "created_at"]
    list_filter = ["source"]
    search_fields = ["email"]
    readonly_fields = ["email", "confirmed_at", "unsubscribed_at", "source"]

from django.contrib import admin

from .models import AnnouncementBar


@admin.register(AnnouncementBar)
class AnnouncementBarAdmin(admin.ModelAdmin):
    list_display = ["text", "is_active", "starts_at", "ends_at", "updated_at"]
    list_filter = ["is_active"]
    fields = ["text", "url", "is_active", "starts_at", "ends_at"]
    search_fields = ["text"]

from django.contrib import admin

from .models import SearchQueryLog


@admin.register(SearchQueryLog)
class SearchQueryLogAdmin(admin.ModelAdmin):
    list_display = ["query", "result_count", "engine", "converted", "created_at"]
    list_filter = ["engine", "converted"]
    search_fields = ["query"]
    readonly_fields = ["query", "result_count", "engine", "converted", "session_key", "created_at"]

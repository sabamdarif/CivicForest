"""Admin for the search tables.

Synonyms are the editable one (decision 6). Documents and the query log are read-only: a
document is derived from the catalogue, and a log row is a record of what someone typed.
"""

from django.contrib import admin

from .models import SearchDocument, SearchQueryLog, SearchSynonym


@admin.register(SearchSynonym)
class SearchSynonymAdmin(admin.ModelAdmin):
    list_display = ["term", "expansion", "is_active"]
    list_editable = ["expansion", "is_active"]
    list_filter = ["is_active"]
    search_fields = ["term", "expansion"]


@admin.register(SearchDocument)
class SearchDocumentAdmin(admin.ModelAdmin):
    list_display = ["product", "is_stale", "updated_at"]
    list_filter = ["is_stale"]
    search_fields = ["product__name", "text"]
    readonly_fields = ["product", "text", "is_stale", "updated_at"]
    exclude = ["vector"]  # a tsvector is not readable, and nothing may edit it by hand

    def has_add_permission(self, request):
        return False


@admin.register(SearchQueryLog)
class SearchQueryLogAdmin(admin.ModelAdmin):
    list_display = ["query", "result_count", "created_at"]
    list_filter = ["result_count"]
    search_fields = ["query"]
    readonly_fields = ["query", "result_count", "session_key", "created_at"]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

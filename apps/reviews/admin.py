from django.contrib import admin

from . import services
from .models import Review


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    """Moderation is normally the back-office queue (M9.2); this admin is the fallback. Publishing
    or rejecting here goes through the service so the product's cached rating is recomputed."""

    list_display = ["product", "rating", "status", "fit_feedback", "user", "created_at"]
    list_filter = ["status", "rating", "fit_feedback"]
    search_fields = ["product__name", "user__email", "title", "body"]
    readonly_fields = ["product", "user", "order_item", "published_at"]
    actions = ["publish", "reject"]

    @admin.action(description="Publish selected reviews")
    def publish(self, request, queryset):
        for review in queryset:
            services.publish_review(review)

    @admin.action(description="Reject selected reviews")
    def reject(self, request, queryset):
        for review in queryset:
            services.reject_review(review)

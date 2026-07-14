from django.contrib import admin

from .models import CustomDesignOrder


@admin.register(CustomDesignOrder)
class CustomDesignOrderAdmin(admin.ModelAdmin):
    list_display = [
        "idempotency_key",
        "user",
        "order",
        "review_status",
        "submit_status",
        "qikink_status",
        "tracking_awb",
        "created_at",
    ]
    list_filter = ["review_status", "submit_status"]
    search_fields = ["idempotency_key", "user__email", "qikink_order_id", "order__order_number"]
    raw_id_fields = ["user", "order", "variant"]
    readonly_fields = ["idempotency_key", "qikink_order_id", "submitted_at", "created_at"]
    # A staff member can flip review_status (approve/reject) — the manual review gate.
    actions = ["mark_approved", "mark_rejected"]

    @admin.action(description="Approve selected designs for printing")
    def mark_approved(self, request, queryset):
        queryset.update(review_status=CustomDesignOrder.ReviewStatus.APPROVED)

    @admin.action(description="Reject selected designs")
    def mark_rejected(self, request, queryset):
        queryset.update(review_status=CustomDesignOrder.ReviewStatus.REJECTED)

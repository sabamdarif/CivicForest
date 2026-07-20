from django.contrib import admin, messages

from .models import CustomDesignOrder
from .tasks import submit_custom_order_to_qikink


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
    actions = ["mark_approved", "mark_rejected", "retry_submission"]

    @admin.action(description="Approve selected designs for printing")
    def mark_approved(self, request, queryset):
        queryset.update(review_status=CustomDesignOrder.ReviewStatus.APPROVED)
        # A design flagged at payment time missed the webhook's submission — enqueue it
        # now (bugs.md #4). submit_to_qikink is idempotent and re-checks paid/review
        # state, so over-enqueueing here is harmless.
        self._enqueue_paid(request, queryset)

    @admin.action(description="Retry Qikink submission")
    def retry_submission(self, request, queryset):
        self._enqueue_paid(request, queryset)

    def _enqueue_paid(self, request, queryset):
        enqueued = 0
        for custom in queryset.select_related("order"):
            if custom.order is not None and custom.order.is_paid and not custom.qikink_order_id:
                submit_custom_order_to_qikink.delay(str(custom.id))
                enqueued += 1
        if enqueued:
            self.message_user(
                request, f"Enqueued {enqueued} Qikink submission(s).", messages.SUCCESS
            )

    @admin.action(description="Reject selected designs")
    def mark_rejected(self, request, queryset):
        queryset.update(review_status=CustomDesignOrder.ReviewStatus.REJECTED)

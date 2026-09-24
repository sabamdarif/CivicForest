"""Admin for the custom-print line.

Design review acts on ``DesignUpload`` (the artwork), because a design is reusable and is
judged once. The Qikink submission and its retry act on ``CustomDesignOrder``. The customer-
facing moderation queue and its emails are surfaced in the back-office (M8.6); these actions
are the staff gate until then."""

from django.contrib import admin, messages

from apps.common.email import send_design_review_email

from . import services
from .models import CustomBlank, CustomDesignOrder, DesignUpload


@admin.register(CustomBlank)
class CustomBlankAdmin(admin.ModelAdmin):
    list_display = ["slug", "product", "print_type_id", "display_order", "is_active"]
    list_filter = ["is_active"]
    search_fields = ["slug", "product__name"]
    raw_id_fields = ["product"]
    prepopulated_fields = {"slug": ["tagline"]}


@admin.register(DesignUpload)
class DesignUploadAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "user",
        "status",
        "review_status",
        "width_px",
        "height_px",
        "dpi_estimate",
        "created_at",
    ]
    list_filter = ["status", "review_status"]
    search_fields = ["id", "user__email", "r2_key_print"]
    raw_id_fields = ["user"]
    readonly_fields = [
        "r2_key_raw",
        "r2_key_print",
        "r2_key_mockup",
        "mime",
        "bytes",
        "width_px",
        "height_px",
        "dpi_estimate",
        "sanitised_at",
        "created_at",
    ]
    actions = ["mark_approved", "mark_rejected"]

    @admin.action(description="Approve selected designs for printing")
    def mark_approved(self, request, queryset):
        count = 0
        for design in queryset:
            design.review_status = DesignUpload.ReviewStatus.APPROVED
            design.save(update_fields=["review_status", "updated_at"])
            send_design_review_email(str(design.id), "approved")
            # A design approved after payment missed the webhook's submission window; submit any
            # paid line now. submit_paid_design is idempotent and re-checks paid + review state.
            for custom in design.front_orders.all():
                if custom.order_id and custom.order.is_paid:
                    services.submit_paid_design(custom)
            count += 1
        self.message_user(request, f"Approved {count} design(s).", messages.SUCCESS)

    @admin.action(description="Reject selected designs")
    def mark_rejected(self, request, queryset):
        count = 0
        for design in queryset:
            design.review_status = DesignUpload.ReviewStatus.REJECTED
            design.save(update_fields=["review_status", "updated_at"])
            send_design_review_email(str(design.id), "rejected")
            count += 1
        self.message_user(request, f"Rejected {count} design(s).", messages.WARNING)


@admin.register(CustomDesignOrder)
class CustomDesignOrderAdmin(admin.ModelAdmin):
    list_display = [
        "idempotency_key",
        "user",
        "order",
        "submit_status",
        "qikink_status",
        "tracking_awb",
        "created_at",
    ]
    list_filter = ["submit_status"]
    search_fields = ["idempotency_key", "user__email", "qikink_order_id", "order__order_number"]
    raw_id_fields = ["user", "order", "blank_variant", "design_upload", "back_design_upload"]
    readonly_fields = [
        "idempotency_key",
        "qikink_order_id",
        "submitted_at",
        "qikink_last_polled_at",
        "retry_count",
        "last_error",
        "created_at",
    ]
    actions = ["retry_submission"]

    @admin.action(description="Retry Qikink submission")
    def retry_submission(self, request, queryset):
        submitted = 0
        for custom in queryset.select_related("order"):
            if custom.order is not None and custom.order.is_paid and not custom.qikink_order_id:
                if services.submit_paid_design(custom) == "submitted":
                    submitted += 1
        if submitted:
            self.message_user(request, f"Submitted {submitted} Qikink order(s).", messages.SUCCESS)

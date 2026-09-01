from django.contrib import admin

from .models import Payment, WebhookEvent


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = [
        "gateway_order_id",
        "order",
        "amount",
        "currency",
        "status",
        "verified_at",
    ]
    list_filter = ["status", "gateway"]
    search_fields = ["gateway_order_id", "gateway_payment_id", "order__order_number"]
    raw_id_fields = ["order"]
    readonly_fields = [f.name for f in Payment._meta.fields]


@admin.register(WebhookEvent)
class WebhookEventAdmin(admin.ModelAdmin):
    list_display = ["gateway", "event_id", "event_type", "processed", "created_at"]
    list_filter = ["gateway", "event_type", "processed"]
    search_fields = ["event_id"]
    readonly_fields = [f.name for f in WebhookEvent._meta.fields]

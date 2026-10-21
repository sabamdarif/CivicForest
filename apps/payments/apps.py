from django.apps import AppConfig


class PaymentsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.payments"

    def ready(self):
        # Audit the money records: the payment rows and the webhook dedup ledger (O12).
        from auditlog.registry import auditlog

        from .models import Payment, WebhookEvent

        auditlog.register(Payment)
        auditlog.register(WebhookEvent)

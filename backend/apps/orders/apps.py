from django.apps import AppConfig


class OrdersConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.orders"

    def ready(self):
        # Audit trail on order status changes (who moved it, when — plan.md §11).
        from auditlog.registry import auditlog

        from .models import Order

        auditlog.register(Order)

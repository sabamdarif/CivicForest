from django.apps import AppConfig


class OrdersConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.orders"

    def ready(self):
        # Audit trail on order status changes (who moved it and when, plan.md §11), and on returns,
        # which move money and stock (M9.3).
        from auditlog.registry import auditlog

        from .models import Order, ReturnRequest

        auditlog.register(Order)
        auditlog.register(ReturnRequest)

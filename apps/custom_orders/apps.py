from django.apps import AppConfig


class CustomOrdersConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.custom_orders"

    def ready(self):
        # Audit the custom-print records: the design uploads and the Qikink line orders (O12).
        from auditlog.registry import auditlog

        from .models import CustomDesignOrder, DesignUpload

        auditlog.register(CustomDesignOrder)
        auditlog.register(DesignUpload)

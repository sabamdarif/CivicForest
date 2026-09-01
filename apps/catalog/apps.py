from django.apps import AppConfig


class CatalogConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.catalog"

    def ready(self):
        # Field-level audit trail on price/stock-bearing catalog models (plan.md §11).
        from auditlog.registry import auditlog

        from .models import Product, ProductVariant

        auditlog.register(Product)
        auditlog.register(ProductVariant)

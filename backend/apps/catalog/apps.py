from django.apps import AppConfig


class CatalogConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.catalog"

    def ready(self):
        # Register search-index sync signals (import for side effects).
        # Field-level audit trail on price/stock-bearing catalog models (plan.md §11).
        from auditlog.registry import auditlog

        from apps.search import signals  # noqa: F401

        from .models import Product, ProductVariant

        auditlog.register(Product)
        auditlog.register(ProductVariant)

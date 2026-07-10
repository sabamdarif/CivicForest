from django.apps import AppConfig


class CatalogConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.catalog"

    def ready(self):
        # Register search-index sync signals (import for side effects).
        from apps.search import signals  # noqa: F401

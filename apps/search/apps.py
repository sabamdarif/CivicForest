from django.apps import AppConfig


class SearchConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.search"

    def ready(self):
        # Catalogue edits have to mark documents stale, so the receivers must be connected
        # for every entry point: the admin, a command, a test (M3 task 3).
        from . import signals  # noqa: F401

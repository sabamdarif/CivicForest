from django.apps import AppConfig


class AccountsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.accounts"

    def ready(self):
        # Register the welcome-email receiver on allauth's email_confirmed signal.
        from . import signals  # noqa: F401

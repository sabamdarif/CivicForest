from django.apps import AppConfig


class AccountsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.accounts"

    def ready(self):
        # Register the welcome-email receiver on allauth's email_confirmed signal.
        # Field-level audit trail on the customer identity and address rows (O12).
        from auditlog.registry import auditlog

        from . import signals  # noqa: F401
        from .models import Address, User

        auditlog.register(User)
        auditlog.register(Address)

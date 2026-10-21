"""Staff operations surface: views and templates over models the other apps own.

This app holds no domain models of its own (the run-ledger models in M8.13 live in
``apps.common``). Every page sits behind ``StaffRequiredMixin`` (``is_staff`` plus a confirmed
TOTP step) and an optional per-view permission, so authorization is uniform and never a 302 that
confirms a page exists.
"""

from django.apps import AppConfig


class BackofficeConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.backoffice"

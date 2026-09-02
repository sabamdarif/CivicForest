from django.apps import AppConfig


class ContentConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.content"

    def ready(self):
        # The bar is customer-facing copy any staff member can change, so who changed it
        # is worth recording (O12).
        from auditlog.registry import auditlog

        from .models import AnnouncementBar

        auditlog.register(AnnouncementBar)

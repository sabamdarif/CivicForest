from django.apps import AppConfig


class ContentConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.content"

    def ready(self):
        # Customer-facing copy any staff member can change, so who changed it is worth recording
        # (O12). The contact and newsletter rows are customer-generated, not staff edits, so they
        # are left out: auditing every signup would be noise, not an audit trail.
        from auditlog.registry import auditlog

        from .models import AnnouncementBar, FaqEntry, Page

        auditlog.register(AnnouncementBar)
        auditlog.register(Page)
        auditlog.register(FaqEntry)

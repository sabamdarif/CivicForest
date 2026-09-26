from django.apps import AppConfig


class ReviewsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.reviews"

    def ready(self):
        # A review is customer-facing content that changes what the product page claims and is
        # moderated by staff, so who published or hid one is worth recording (O12).
        from auditlog.registry import auditlog

        from .models import Review

        auditlog.register(Review)

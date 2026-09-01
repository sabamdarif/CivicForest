from django.apps import AppConfig


class CartConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.cart"

    def ready(self):
        # Merge a guest's session cart into their user cart on login (import for
        # side effects — registers the allauth signal receiver).
        # Audit trail on coupon changes (discount value is money-sensitive — plan.md §11).
        from auditlog.registry import auditlog

        from . import signals  # noqa: F401
        from .models import Coupon

        auditlog.register(Coupon)

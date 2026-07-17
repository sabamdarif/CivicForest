"""Task discovery shim — Celery autodiscovers ``<app>.tasks``, so re-export the
email task defined in ``email.py`` here to register it on the worker."""

from .email import send_order_email

__all__ = ["send_order_email"]

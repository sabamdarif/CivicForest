"""Local development settings.

Plain HTTP on localhost, so the Secure cookie flags production sets stay off here. A
template variable typo fails loudly instead of rendering an empty string.
"""

from jinja2 import StrictUndefined

from .base import *  # noqa: F403
from .base import TEMPLATES, env

DEBUG = env("DJANGO_DEBUG", default=True)
ALLOWED_HOSTS = ["localhost", "127.0.0.1", "[::1]", ".vercel.app"]
CSRF_TRUSTED_ORIGINS = ["http://localhost:8000", "http://127.0.0.1:8000"]

EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

TEMPLATES[0]["OPTIONS"]["undefined"] = StrictUndefined

INTERNAL_IPS = ["127.0.0.1"]

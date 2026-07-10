"""Production settings.

Layers strict transport security and HSTS on top of the already-secure base. Secrets
come only from the environment (a real secrets manager in production — plan.md §12).
"""

from .base import *  # noqa: F403
from .base import env

DEBUG = False

# Fail loud if the secret wasn't provided — never fall back to a dev key in prod.
SECRET_KEY = env("DJANGO_SECRET_KEY")

SECURE_SSL_REDIRECT = True
SECURE_HSTS_SECONDS = 60 * 60 * 24 * 365  # 1 year
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True

# Shorter idle window for everyone; staff hardening (even shorter) handled per-session.
SESSION_COOKIE_AGE = 60 * 60 * 24 * 7  # 1 week

# Structured JSON logs for aggregation; correlation IDs threaded in later (plan.md §16).
LOGGING["root"]["level"] = "INFO"  # noqa: F405

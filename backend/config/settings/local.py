"""Local development settings.

HTTPS is still on locally (Caddy + mkcert), so cookie/security flags stay identical
to production. The only real relaxations here are DEBUG, a permissive email backend,
and a SQLite fallback so the project boots without a running Postgres for quick checks.
"""

from .base import *  # noqa: F403
from .base import CORS_ALLOWED_ORIGINS, CSRF_TRUSTED_ORIGINS, env

DEBUG = env("DJANGO_DEBUG", default=True)

# Boot without external services (Postgres/Redis/Meili) for `manage.py check`,
# the offline test run, and quick local work when USE_SQLITE=1.
OFFLINE = env.bool("USE_SQLITE", default=False)

# Ensure local origins (http://localhost:3000, http://127.0.0.1:3000) are allowed in local dev
_dev_origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
]
for origin in _dev_origins:
    if origin not in CORS_ALLOWED_ORIGINS:
        CORS_ALLOWED_ORIGINS.append(origin)
    if origin not in CSRF_TRUSTED_ORIGINS:
        CSRF_TRUSTED_ORIGINS.append(origin)

if OFFLINE:
    SESSION_COOKIE_SECURE = False
    CSRF_COOKIE_SECURE = False
    SESSION_COOKIE_DOMAIN = None
    # Bare runserver + `next dev` — no Caddy, so the frontend is plain localhost.
    FRONTEND_ORIGIN = "http://localhost:3000"
    HEADLESS_FRONTEND_URLS = {
        "account_confirm_email": FRONTEND_ORIGIN + "/account/verify-email/{key}",
        "account_reset_password": FRONTEND_ORIGIN + "/account/password/reset",
        "account_reset_password_from_key": FRONTEND_ORIGIN + "/account/password/reset/key/{key}",
        "account_signup": FRONTEND_ORIGIN + "/signup",
    }
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",  # noqa: F405
        }
    }
    CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
    SESSION_ENGINE = "django.contrib.sessions.backends.db"
    # No Meili in offline mode — search transparently uses the Postgres fallback,
    # so the index-sync task returns instantly instead of waiting on TCP timeouts.
    MEILISEARCH_URL = ""  # noqa: F811
    # Force local-disk storage offline even if S3_BUCKET_NAME is set in .env —
    # object storage needs credentials the offline/test run doesn't have.
    STORAGES = {  # noqa: F405
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
    }

EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

# Eager Celery runs signal→index sync inline (no broker needed). On by default in
# offline mode so tests and no-worker dev don't hit Redis; override with the env var.
CELERY_TASK_ALWAYS_EAGER = env.bool("CELERY_TASK_ALWAYS_EAGER", default=OFFLINE)

INTERNAL_IPS = ["127.0.0.1"]

"""E2E test settings (Playwright, plan.md §12) — NEVER use in production.

Runs the real app over plain http://localhost without Caddy/TLS, so the two secure
cookie flags are relaxed — everything else stays identical to local. Razorpay is
fake-moded (no network); the webhook secret is a known constant so the E2E suite can
sign genuine webhooks and exercise the real fulfilment path.
"""

from .local import *  # noqa: F401,F403
from .local import BASE_DIR

DEBUG = True

# Playwright can't read verification codes out of the console email backend, so
# signup logs straight in here; the OTP flow is covered by manual/local testing.
# (by-code must be off too — allauth requires it be paired with "mandatory".)
ACCOUNT_EMAIL_VERIFICATION = "optional"
ACCOUNT_EMAIL_VERIFICATION_BY_CODE_ENABLED = False

DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": BASE_DIR / "e2e.sqlite3"}}
CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
SESSION_ENGINE = "django.contrib.sessions.backends.db"
MEILISEARCH_URL = ""  # Postgres/SQLite icontains fallback
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}
CELERY_TASK_ALWAYS_EAGER = True
MEDIA_ROOT = BASE_DIR / "e2e_media"  # ./mediafiles may be root-owned from Docker runs

# http://localhost has no TLS; Chrome still treats it as trustworthy.
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False
# .env sets Domain=.civicforest.local for the Docker/Caddy stack — a localhost
# browser rejects such a cookie outright, so no session would ever persist here.
SESSION_COOKIE_DOMAIN = None

FRONTEND_ORIGIN = "http://localhost:3001"
CORS_ALLOWED_ORIGINS = ["http://localhost:3001"]
CSRF_TRUSTED_ORIGINS = ["http://localhost:3001", "http://localhost:8001"]
ALLOWED_HOSTS = ["localhost", "127.0.0.1"]

RAZORPAY_KEY_ID = "rzp_test_e2e"
RAZORPAY_KEY_SECRET = "e2e-key-secret"
RAZORPAY_WEBHOOK_SECRET = "e2e-webhook-secret"  # the Playwright suite signs with this
RAZORPAY_FAKE_MODE = True  # gateway.create_order returns a canned order, no network

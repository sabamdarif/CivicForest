"""
Base settings shared by every environment.

Everything here reads from the environment (django-environ). Environment-specific
overrides live in ``local.py`` / ``production.py``. Security-relevant flags are set
identically everywhere because HTTPS is on in dev and prod alike — see plan.md §13.
"""

from pathlib import Path

import environ

# backend/config/settings/base.py -> backend/
BASE_DIR = Path(__file__).resolve().parent.parent.parent

env = environ.Env(
    DJANGO_DEBUG=(bool, False),
    DJANGO_ALLOWED_HOSTS=(list, []),
    CORS_ALLOWED_ORIGINS=(list, []),
    CSRF_TRUSTED_ORIGINS=(list, []),
)

# Read a local .env if present (compose passes real env vars in containers).
env_file = BASE_DIR.parent / ".env"
if env_file.exists():
    env.read_env(str(env_file))

# No default — every environment (dev included) must set it in .env (bugs.md #13).
SECRET_KEY = env("DJANGO_SECRET_KEY")
DEBUG = env("DJANGO_DEBUG")
ALLOWED_HOSTS = env("DJANGO_ALLOWED_HOSTS")

# ─── Applications ────────────────────────────────────────────────────────────
DJANGO_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.sites",
]

THIRD_PARTY_APPS = [
    "rest_framework",
    "corsheaders",
    "django_filters",
    "drf_spectacular",
    "allauth",
    "allauth.account",
    "allauth.headless",
    "allauth.mfa",
    "allauth.socialaccount",
    "allauth.socialaccount.providers.google",
    "django_celery_beat",
    "auditlog",
]

LOCAL_APPS = [
    "apps.common",
    "apps.accounts",
    "apps.catalog",
    "apps.search",
    "apps.cart",
    "apps.orders",
    "apps.payments",
    "apps.custom_orders",
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

# ─── Middleware ──────────────────────────────────────────────────────────────
MIDDLEWARE = [
    "apps.common.middleware.RequestIDMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "allauth.account.middleware.AccountMiddleware",
    # After auth (needs request.user) — gates the admin path on staff MFA.
    "apps.common.middleware.StaffAdminMiddleware",
    # auditlog: records which user made a change (before/after diffs on registered models).
    "auditlog.middleware.AuditlogMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

# ─── Database ────────────────────────────────────────────────────────────────
DATABASES = {
    "default": env.db(
        "DATABASE_URL",
        default="postgres://civicforest:civicforest@postgres:5432/civicforest",
    ),
}
DATABASES["default"]["ATOMIC_REQUESTS"] = False
DATABASES["default"]["CONN_MAX_AGE"] = 60

# ─── Cache / Redis ───────────────────────────────────────────────────────────
REDIS_URL = env("REDIS_URL", default="redis://redis:6379/0")
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": REDIS_URL,
    }
}

# ─── Auth ────────────────────────────────────────────────────────────────────
AUTH_USER_MODEL = "accounts.User"
SITE_ID = 1

AUTHENTICATION_BACKENDS = [
    "django.contrib.auth.backends.ModelBackend",
    "allauth.account.auth_backends.AuthenticationBackend",
]

# Argon2id first — stronger against GPU cracking than the PBKDF2 default (plan.md §5).
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.Argon2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2SHA1PasswordHasher",
    "django.contrib.auth.hashers.BCryptSHA256PasswordHasher",
]

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 10},
    },
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# ─── allauth ─────────────────────────────────────────────────────────────────
ACCOUNT_LOGIN_METHODS = {"email"}
ACCOUNT_SIGNUP_FIELDS = ["email*", "password1*", "password2*"]
# The custom User model has no username field — without this, allauth's signup
# form crashes looking it up (FieldDoesNotExist → 500 on /auth/signup).
ACCOUNT_USER_MODEL_USERNAME_FIELD = None
# One email per account; changing it stages the new address until verified.
ACCOUNT_CHANGE_EMAIL = True
# Verify email with a short code (OTP) typed into the SPA instead of a link —
# powers both signup verification and the change-email flow on /account/profile.
ACCOUNT_EMAIL_VERIFICATION_BY_CODE_ENABLED = True
# "mandatory" — allauth's email-enumeration prevention only fully works in this mode;
# "optional" makes duplicate-email signups distinguishable (bugs.md #5).
ACCOUNT_EMAIL_VERIFICATION = "mandatory"
ACCOUNT_UNIQUE_EMAIL = True
# Tighter than allauth's 30/min default on the credential-guessing surface (bugs.md #6).
ACCOUNT_RATE_LIMITS = {
    "login_failed": "10/5m/ip,5/5m/key",
    "reset_password": "5/5m/ip,3/5m/key",
    "signup": "10/5m/ip",
}
ACCOUNT_SESSION_REMEMBER = None  # honor the "remember me" checkbox from the client

# Headless mode powers the Next.js frontend. The frontend URLs let allauth build
# correct email/redirect links back into the SPA.
HEADLESS_ONLY = True
FRONTEND_ORIGIN = env("FRONTEND_ORIGIN", default="https://civicforest.local")
HEADLESS_FRONTEND_URLS = {
    "account_confirm_email": FRONTEND_ORIGIN + "/account/verify-email/{key}",
    "account_reset_password": FRONTEND_ORIGIN + "/account/password/reset",
    "account_reset_password_from_key": FRONTEND_ORIGIN + "/account/password/reset/key/{key}",
    "account_signup": FRONTEND_ORIGIN + "/signup",
}

MFA_SUPPORTED_TYPES = ["totp", "recovery_codes"]

SOCIALACCOUNT_PROVIDERS = {
    "google": {
        "APP": {
            "client_id": env("GOOGLE_OAUTH_CLIENT_ID", default=""),
            "secret": env("GOOGLE_OAUTH_CLIENT_SECRET", default=""),
            "key": "",
        },
        "SCOPE": ["profile", "email"],
        "AUTH_PARAMS": {"access_type": "online"},
    }
}

# ─── DRF ─────────────────────────────────────────────────────────────────────
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticatedOrReadOnly",
    ],
    "DEFAULT_PAGINATION_CLASS": "apps.common.pagination.StandardResultsPagination",
    "PAGE_SIZE": 12,
    "DEFAULT_FILTER_BACKENDS": [
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.OrderingFilter",
    ],
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
        "rest_framework.throttling.ScopedRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "anon": "120/min",
        "user": "600/min",
        # Auth endpoints are allauth headless (not DRF) — rate-limited via
        # ACCOUNT_RATE_LIMITS below, not here (bugs.md #6).
        "search": "60/min",  # autocomplete suggestion endpoint
    },
    "EXCEPTION_HANDLER": "apps.common.exceptions.standard_exception_handler",
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
}

SPECTACULAR_SETTINGS = {
    "TITLE": "CivicForest API",
    "DESCRIPTION": "Internal storefront API. Not exposed publicly in production.",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
}

# ─── CORS / CSRF ─────────────────────────────────────────────────────────────
# Explicit allow-list only — credentials (cookies) are involved, never use "*".
CORS_ALLOWED_ORIGINS = env("CORS_ALLOWED_ORIGINS")
CORS_ALLOW_CREDENTIALS = True
CSRF_TRUSTED_ORIGINS = env("CSRF_TRUSTED_ORIGINS")

# ─── Sessions & cookie security ──────────────────────────────────────────────
# Secure everywhere — HTTPS is on in dev too, so no `if DEBUG` branching (plan.md §13).
SESSION_COOKIE_SECURE = True
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_DOMAIN = env("SESSION_COOKIE_DOMAIN", default=None)
SESSION_COOKIE_AGE = 60 * 60 * 24 * 14  # 2 weeks
SESSION_ENGINE = "django.contrib.sessions.backends.cached_db"

CSRF_COOKIE_SECURE = True
CSRF_COOKIE_HTTPONLY = False  # JS must read the token to echo it back
CSRF_COOKIE_SAMESITE = "Lax"

# ─── Security headers ────────────────────────────────────────────────────────
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# ─── i18n / tz ───────────────────────────────────────────────────────────────
LANGUAGE_CODE = "en-us"
TIME_ZONE = "Asia/Kolkata"
USE_I18N = True
USE_TZ = True

# ─── Static / media ──────────────────────────────────────────────────────────
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "mediafiles"

DATA_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024  # 10 MB request body cap

# ─── Email ───────────────────────────────────────────────────────────────────
# SMTP when EMAIL_HOST is provided (any transactional provider), else console (dev).
# Order emails are sent off the Celery queue so a slow mail server never blocks the
# payment webhook (plan.md §7, §8).
EMAIL_HOST = env("EMAIL_HOST", default="")
if EMAIL_HOST:
    EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
    EMAIL_PORT = env.int("EMAIL_PORT", default=587)
    EMAIL_HOST_USER = env("EMAIL_HOST_USER", default="")
    EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", default="")
    EMAIL_USE_TLS = env.bool("EMAIL_USE_TLS", default=True)
else:
    EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", default="CivicForest <no-reply@civicforest.local>")

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ─── Admin ───────────────────────────────────────────────────────────────────
# Non-guessable admin path from env; never the default /admin/ (plan.md §11).
# Django reads the SAME env var Caddy uses (DJANGO_ADMIN_PATH) so the two can't
# drift (bugs.md #10); the shared default matches Caddy's, so leaving both unset
# serves the admin only on a path Caddy IP-blocks. DJANGO_ADMIN_URL kept as a
# legacy fallback for existing .env files.
ADMIN_URL = env(
    "DJANGO_ADMIN_PATH",
    default=env("DJANGO_ADMIN_URL", default="/__admin_disabled__/"),
).strip("/") + "/"
# Staff sessions expire faster than customer sessions; enforced in StaffAdminMiddleware.
STAFF_SESSION_AGE = env.int("STAFF_SESSION_AGE", default=60 * 60)

# ─── Celery ──────────────────────────────────────────────────────────────────
CELERY_BROKER_URL = env("CELERY_BROKER_URL", default="redis://redis:6379/1")
CELERY_RESULT_BACKEND = env("CELERY_RESULT_BACKEND", default="redis://redis:6379/2")
CELERY_TASK_ALWAYS_EAGER = False
CELERY_TASK_ACKS_LATE = True
CELERY_TASK_REJECT_ON_WORKER_LOST = True
CELERY_BEAT_SCHEDULER = "django_celery_beat.schedulers:DatabaseScheduler"

# ─── Meilisearch ─────────────────────────────────────────────────────────────
MEILISEARCH_URL = env("MEILISEARCH_URL", default="http://meilisearch:7700")
MEILISEARCH_MASTER_KEY = env("MEILISEARCH_MASTER_KEY", default="")
MEILISEARCH_INDEX_PREFIX = env("MEILISEARCH_INDEX_PREFIX", default="civicforest")

# ─── Cart / checkout pricing rules ───────────────────────────────────────────
# Server-side pricing constants — the client never sends shipping or totals.
SHIPPING_FLAT_RATE = env("SHIPPING_FLAT_RATE", default="59.00")
FREE_SHIPPING_THRESHOLD = env("FREE_SHIPPING_THRESHOLD", default="999.00")
CURRENCY = env("CURRENCY", default="INR")

# ─── Payments (Razorpay) ─────────────────────────────────────────────────────
# Never touch raw card data — Razorpay's hosted checkout keeps PCI scope at SAQ-A
# (plan.md §9). The webhook secret is separate from the API secret.
RAZORPAY_KEY_ID = env("RAZORPAY_KEY_ID", default="")
RAZORPAY_KEY_SECRET = env("RAZORPAY_KEY_SECRET", default="")
RAZORPAY_WEBHOOK_SECRET = env("RAZORPAY_WEBHOOK_SECRET", default="")

# ─── Print fulfilment (Qikink Open API) ──────────────────────────────────────
# Base URL and paths are configurable so they can be corrected against Qikink's live
# Postman reference without a code change. Credentials stay server-side only.
QIKINK_BASE_URL = env("QIKINK_BASE_URL", default="https://sandbox.qikink.com")
QIKINK_CLIENT_ID = env("QIKINK_CLIENT_ID", default="")
QIKINK_CLIENT_SECRET = env("QIKINK_CLIENT_SECRET", default="")
QIKINK_TOKEN_PATH = env("QIKINK_TOKEN_PATH", default="/api/token")
QIKINK_ORDER_CREATE_PATH = env("QIKINK_ORDER_CREATE_PATH", default="/api/order/create")
QIKINK_ORDER_STATUS_PATH = env("QIKINK_ORDER_STATUS_PATH", default="/api/order/status")
QIKINK_TOKEN_TTL = env.int("QIKINK_TOKEN_TTL", default=60 * 60)  # cache token ~1h

# ─── Object storage (S3 / Cloudflare R2) ─────────────────────────────────────
# Design uploads must never live on the app disk. When S3_BUCKET_NAME is set the
# default file storage switches to S3-compatible object storage with private ACL and
# signed URLs; otherwise local disk is used for dev (plan.md §8, §12).
S3_BUCKET_NAME = env("S3_BUCKET_NAME", default="")
S3_ACCESS_KEY_ID = env("S3_ACCESS_KEY_ID", default="")
S3_SECRET_ACCESS_KEY = env("S3_SECRET_ACCESS_KEY", default="")
S3_ENDPOINT_URL = env("S3_ENDPOINT_URL", default="")
S3_REGION = env("S3_REGION", default="auto")
DESIGN_UPLOAD_MAX_BYTES = env.int("DESIGN_UPLOAD_MAX_BYTES", default=15 * 1024 * 1024)
DESIGN_UPLOAD_MAX_DIMENSION = env.int("DESIGN_UPLOAD_MAX_DIMENSION", default=8000)

# When a bucket is configured, the default file storage becomes private S3/R2:
# objects are never public, and every URL is a short-lived signed link — so design
# uploads (customer artwork) are only reachable by the print partner, not by guessing
# a URL (plan.md §8, §12). No bucket set ⇒ local disk (dev only).
if S3_BUCKET_NAME:
    if not (S3_ACCESS_KEY_ID and S3_SECRET_ACCESS_KEY):
        from django.core.exceptions import ImproperlyConfigured

        raise ImproperlyConfigured(
            "S3_BUCKET_NAME is set but S3_ACCESS_KEY_ID/S3_SECRET_ACCESS_KEY are not — "
            "either set the keys or unset the bucket to use local disk storage."
        )
    STORAGES["default"] = {
        "BACKEND": "storages.backends.s3.S3Storage",
        "OPTIONS": {
            "bucket_name": S3_BUCKET_NAME,
            "access_key": S3_ACCESS_KEY_ID,
            "secret_key": S3_SECRET_ACCESS_KEY,
            "endpoint_url": S3_ENDPOINT_URL or None,
            "region_name": S3_REGION,
            "default_acl": "private",
            "querystring_auth": True,  # serve via signed URLs
            "querystring_expire": env.int("S3_SIGNED_URL_TTL", default=3600),
            "file_overwrite": False,
            "signature_version": "s3v4",
        },
    }

# ─── Logging (correlation-ID on every line; JSON formatter wired in production) ─
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "filters": {
        "request_id": {"()": "apps.common.middleware.RequestIDLogFilter"},
    },
    "formatters": {
        "verbose": {
            "format": "{levelname} {asctime} {name} [{request_id}] {message}",
            "style": "{",
        },
        "json": {
            "()": "pythonjsonlogger.json.JsonFormatter",
            "format": "%(levelname)s %(asctime)s %(name)s %(request_id)s %(message)s",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "verbose",
            "filters": ["request_id"],
        },
    },
    "root": {"handlers": ["console"], "level": "INFO"},
    "loggers": {
        "django.security": {"handlers": ["console"], "level": "WARNING", "propagate": False},
    },
}

# ─── Error tracking (Sentry) — no-op when SENTRY_DSN is unset ─────────────────
SENTRY_DSN = env("SENTRY_DSN", default="")
if SENTRY_DSN:
    import sentry_sdk
    from sentry_sdk.integrations.celery import CeleryIntegration
    from sentry_sdk.integrations.django import DjangoIntegration

    sentry_sdk.init(
        dsn=SENTRY_DSN,
        integrations=[DjangoIntegration(), CeleryIntegration()],
        traces_sample_rate=env.float("SENTRY_TRACES_SAMPLE_RATE", default=0.1),
        environment=env("SENTRY_ENVIRONMENT", default="development"),
        # PII (emails, card data) must never leave our systems — DPDP Act (plan.md §12).
        send_default_pii=False,
    )

"""Base settings shared by every environment.

Everything reads from the environment through django-environ. Nothing here branches on
DEBUG for security behaviour: transport security, R2 and the manifest static storage are
turned on explicitly by ``production.py`` (rebuild/03-architecture.md §2).
"""

from pathlib import Path

import environ

# config/settings/base.py -> the repo root
BASE_DIR = Path(__file__).resolve().parent.parent.parent

env = environ.Env(
    DJANGO_DEBUG=(bool, False),
    DJANGO_ALLOWED_HOSTS=(list, []),
    CSRF_TRUSTED_ORIGINS=(list, []),
)

# Read a local .env if present; the host supplies real env vars in deployment.
env_file = BASE_DIR / ".env"
if env_file.exists():
    env.read_env(str(env_file))

# No default: every environment, dev included, must set it.
SECRET_KEY = env("DJANGO_SECRET_KEY")
DEBUG = env("DJANGO_DEBUG")
ALLOWED_HOSTS = env("DJANGO_ALLOWED_HOSTS")
CSRF_TRUSTED_ORIGINS = env("CSRF_TRUSTED_ORIGINS")
HEALTH_CHECK_TOKEN = env("HEALTH_CHECK_TOKEN", default="")

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
    "django_filters",
    "allauth",
    "allauth.account",
    "allauth.mfa",
    "allauth.socialaccount",
    "allauth.socialaccount.providers.google",
    "auditlog",
]

LOCAL_APPS = [
    "apps.common",
    "apps.accounts",
    "apps.catalog",
    "apps.cart",
    "apps.orders",
    "apps.payments",
    "apps.custom_orders",
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

# ─── Middleware ──────────────────────────────────────────────────────────────
# WhiteNoise serves collected static files under `vercel dev`; in deployment the Vercel
# CDN serves them and the middleware is a no-op (rebuild/02-research.md §1).
MIDDLEWARE = [
    "apps.common.middleware.RequestIDMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "allauth.account.middleware.AccountMiddleware",
    # After auth (needs request.user): gates the admin path on staff MFA.
    "apps.common.middleware.StaffAdminMiddleware",
    # auditlog: records which user made a change (before/after diffs on registered models).
    "auditlog.middleware.AuditlogMiddleware",
]

ROOT_URLCONF = "config.urls"
# No ASGI_APPLICATION: Vercel prefers ASGI when both exist, and nothing here is async.
WSGI_APPLICATION = "config.wsgi.application"

# Two engines, split by ownership: Jinja2 renders every page we write, the Django
# Template Language renders allauth and the admin, which ship DTL templates and tags.
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.jinja2.Jinja2",
        "DIRS": [BASE_DIR / "templates" / "jinja2"],
        "APP_DIRS": False,
        "OPTIONS": {"environment": "config.jinja2.environment"},
    },
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates" / "django"],
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
    "default": env.db("DATABASE_URL", default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}"),
}
DATABASES["default"]["ATOMIC_REQUESTS"] = False
# Neon pools connections itself, and a serverless instance dies between requests, so
# holding a connection open only exhausts the pool (rebuild/04-build-plan.md risks).
DATABASES["default"]["CONN_MAX_AGE"] = 0

# Forces the local file database even when .env points at Postgres. This is what makes
# the offline test run and `manage.py check` work with no services up.
if env.bool("USE_SQLITE", default=False):
    DATABASES = {
        "default": {"ENGINE": "django.db.backends.sqlite3", "NAME": BASE_DIR / "db.sqlite3"}
    }

# Per-instance cache by default; production swaps in the shared database cache, which is
# what DRF throttling needs to count across function instances.
CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}

# ─── Auth ────────────────────────────────────────────────────────────────────
AUTH_USER_MODEL = "accounts.User"
SITE_ID = 1

AUTHENTICATION_BACKENDS = [
    "django.contrib.auth.backends.ModelBackend",
    "allauth.account.auth_backends.AuthenticationBackend",
]

# Argon2id first: stronger against GPU cracking than the PBKDF2 default.
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
# The custom User model has no username field. Without this, allauth's signup form
# crashes looking it up.
ACCOUNT_USER_MODEL_USERNAME_FIELD = None
# One email per account; changing it stages the new address until verified.
ACCOUNT_CHANGE_EMAIL = True
ACCOUNT_EMAIL_VERIFICATION_BY_CODE_ENABLED = True
# "mandatory": allauth's email-enumeration prevention only fully works in this mode.
ACCOUNT_EMAIL_VERIFICATION = "mandatory"
ACCOUNT_UNIQUE_EMAIL = True
# Tighter than allauth's 30/min default on the credential-guessing surface.
ACCOUNT_RATE_LIMITS = {
    "login_failed": "10/5m/ip,5/5m/key",
    "reset_password": "5/5m/ip,3/5m/key",
    "signup": "10/5m/ip",
    "manage_email": "5/5m/key",
    "change_password": "5/5m/key",
    "reauthenticate": "5/5m/user",
}
ACCOUNT_SESSION_REMEMBER = None  # honour the "remember me" checkbox

MFA_SUPPORTED_TYPES = ["totp", "recovery_codes"]
MFA_TOTP_ISSUER = "CivicForest"

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
# Internal JSON for this site's own scripts: session cookie plus CSRF, same origin, no
# public schema (decision A13).
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
        # Auth endpoints are allauth's, rate-limited via ACCOUNT_RATE_LIMITS above.
        "search": "60/min",
        "checkout": "10/min",
        "checkout_day": "60/day",
        "custom_order_create": "20/hour",
    },
    "EXCEPTION_HANDLER": "apps.common.exceptions.standard_exception_handler",
}

# ─── Sessions & cookie security ──────────────────────────────────────────────
# Secure flags are set in production.py, because local development is plain HTTP and a
# Secure cookie would never be stored.
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_AGE = 60 * 60 * 24 * 14  # 2 weeks (decision B9)
SESSION_ENGINE = "django.contrib.sessions.backends.db"

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
STATICFILES_DIRS = [BASE_DIR / "static"]
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "mediafiles"

# Vercel rejects a request body over 4.5 MB before it reaches Django, so a larger cap
# here would only be a lie. Artwork is uploaded straight to R2 instead.
DATA_UPLOAD_MAX_MEMORY_SIZE = 4 * 1024 * 1024

# ─── Email ───────────────────────────────────────────────────────────────────
# Console in development, Resend over SMTP in production (decision A4).
EMAIL_HOST = env("EMAIL_HOST", default="")
if EMAIL_HOST:
    EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
    EMAIL_PORT = env.int("EMAIL_PORT", default=587)
    EMAIL_HOST_USER = env("EMAIL_HOST_USER", default="")
    EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", default="")
    EMAIL_USE_TLS = env.bool("EMAIL_USE_TLS", default=True)
else:
    EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", default="CivicForest <no-reply@civicforest.com>")
SUPPORT_EMAIL = env("SUPPORT_EMAIL", default=DEFAULT_FROM_EMAIL)

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ─── Admin ───────────────────────────────────────────────────────────────────
# Non-guessable admin path from the environment, never the default /admin/. Left unset
# it serves on a path nobody can reach by guessing.
ADMIN_URL = env("DJANGO_ADMIN_URL", default="__admin_disabled__/").strip("/") + "/"
# Staff sessions expire faster than customer sessions (StaffAdminMiddleware enforces it).
STAFF_SESSION_AGE = env.int("STAFF_SESSION_AGE", default=60 * 60)

# ─── Cart / checkout pricing rules ───────────────────────────────────────────
# Server-side pricing constants: the client never sends shipping or totals.
SHIPPING_FLAT_RATE = env("SHIPPING_FLAT_RATE", default="79.00")
FREE_SHIPPING_THRESHOLD = env("FREE_SHIPPING_THRESHOLD", default="999.00")
CURRENCY = env("CURRENCY", default="INR")

# ─── Payments (Razorpay) ─────────────────────────────────────────────────────
# Raw card data never reaches this app; Razorpay's hosted checkout keeps PCI scope at
# SAQ-A. The webhook secret is separate from the API secret.
RAZORPAY_KEY_ID = env("RAZORPAY_KEY_ID", default="")
RAZORPAY_KEY_SECRET = env("RAZORPAY_KEY_SECRET", default="")
RAZORPAY_WEBHOOK_SECRET = env("RAZORPAY_WEBHOOK_SECRET", default="")

# ─── Print fulfilment (Qikink Open API) ──────────────────────────────────────
# Base URL and paths are configurable so they can be corrected against Qikink's own
# Postman reference without a deploy. Credentials stay server-side only.
QIKINK_BASE_URL = env("QIKINK_BASE_URL", default="https://sandbox.qikink.com")
QIKINK_CLIENT_ID = env("QIKINK_CLIENT_ID", default="")
QIKINK_CLIENT_SECRET = env("QIKINK_CLIENT_SECRET", default="")
QIKINK_TOKEN_PATH = env("QIKINK_TOKEN_PATH", default="/api/token")
QIKINK_ORDER_CREATE_PATH = env("QIKINK_ORDER_CREATE_PATH", default="/api/order/create")
QIKINK_ORDER_STATUS_PATH = env("QIKINK_ORDER_STATUS_PATH", default="/api/order/status")
QIKINK_TOKEN_TTL = env.int("QIKINK_TOKEN_TTL", default=60 * 60)

# ─── Object storage (Cloudflare R2) ──────────────────────────────────────────
# Read here so one place documents them; production.py is what points file storage at
# R2. Local development and tests stay on disk, which needs no credentials.
S3_BUCKET_NAME = env("S3_BUCKET_NAME", default="")
S3_PRIVATE_BUCKET_NAME = env("S3_PRIVATE_BUCKET_NAME", default="")
S3_ACCESS_KEY_ID = env("S3_ACCESS_KEY_ID", default="")
S3_SECRET_ACCESS_KEY = env("S3_SECRET_ACCESS_KEY", default="")
S3_ENDPOINT_URL = env("S3_ENDPOINT_URL", default="")
S3_REGION = env("S3_REGION", default="auto")
S3_SIGNED_URL_TTL = env.int("S3_SIGNED_URL_TTL", default=3600)
R2_PUBLIC_BASE_URL = env("R2_PUBLIC_BASE_URL", default="")
DESIGN_UPLOAD_MAX_BYTES = env.int("DESIGN_UPLOAD_MAX_BYTES", default=15 * 1024 * 1024)
DESIGN_UPLOAD_MAX_DIMENSION = env.int("DESIGN_UPLOAD_MAX_DIMENSION", default=8000)

# ─── Logging (correlation ID on every line; JSON formatter wired in production) ─
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

# ─── Error tracking (Sentry), a no-op when SENTRY_DSN is unset ────────────────
SENTRY_DSN = env("SENTRY_DSN", default="")
if SENTRY_DSN:
    import sentry_sdk
    from sentry_sdk.integrations.django import DjangoIntegration

    sentry_sdk.init(
        dsn=SENTRY_DSN,
        integrations=[DjangoIntegration()],
        traces_sample_rate=env.float("SENTRY_TRACES_SAMPLE_RATE", default=0.1),
        environment=env("SENTRY_ENVIRONMENT", default="development"),
        # PII (emails, addresses) must never leave our systems under the DPDP Act.
        send_default_pii=False,
    )

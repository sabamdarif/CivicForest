"""Production settings: Neon, R2, Resend and transport security.

Secrets come only from the environment. Every value here without a default is one the
deployment must supply, so a missing variable fails the boot instead of quietly falling
back to a development value.
"""

from .base import *  # noqa: F403
from .base import (  # noqa: F401
    S3_ACCESS_KEY_ID,
    S3_BUCKET_NAME,
    S3_ENDPOINT_URL,
    S3_REGION,
    S3_SECRET_ACCESS_KEY,
    S3_SIGNED_URL_TTL,
    env,
)

DEBUG = False

# Fail loud if the secret was not provided: never fall back to a dev key here.
SECRET_KEY = env("DJANGO_SECRET_KEY")

# Neon's pooled connection string. CONN_MAX_AGE stays 0 (set in base) because a
# serverless instance cannot reuse a connection between invocations anyway.
DATABASES = {"default": env.db("DATABASE_URL")}
DATABASES["default"]["ATOMIC_REQUESTS"] = False
DATABASES["default"]["CONN_MAX_AGE"] = 0

# A shared cache, not a per-instance one: DRF throttle counters and allauth's rate
# limits are worthless if every function instance keeps its own. Needs one
# `manage.py createcachetable` after the first migrate.
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.db.DatabaseCache",
        "LOCATION": "django_cache",
    }
}

SECURE_SSL_REDIRECT = True
SECURE_HSTS_SECONDS = 60 * 60 * 24 * 365  # 1 year
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True

# Customer artwork lives in this bucket, so it is never public: every URL is a
# short-lived signed link. R2 has no object ACLs, hence default_acl=None. The public
# product-image bucket and its CDN hostname arrive with the catalogue milestone.
STORAGES = {
    "default": {
        "BACKEND": "storages.backends.s3.S3Storage",
        "OPTIONS": {
            "bucket_name": S3_BUCKET_NAME,
            "access_key": S3_ACCESS_KEY_ID,
            "secret_key": S3_SECRET_ACCESS_KEY,
            "endpoint_url": S3_ENDPOINT_URL or None,
            "region_name": S3_REGION,
            "default_acl": None,
            "querystring_auth": True,
            "querystring_expire": S3_SIGNED_URL_TTL,
            "file_overwrite": False,
            "signature_version": "s3v4",
        },
    },
    # Hashed filenames so the CDN can cache them forever. Vercel runs collectstatic
    # during the build and serves the result (rebuild/02-research.md §1).
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.ManifestStaticFilesStorage",
    },
}

# Resend over SMTP, which needs no code of its own (decision A4).
EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = env("EMAIL_HOST", default="smtp.resend.com")
EMAIL_PORT = env.int("EMAIL_PORT", default=587)
EMAIL_HOST_USER = env("EMAIL_HOST_USER", default="resend")
EMAIL_HOST_PASSWORD = env("RESEND_API_KEY", default="")
EMAIL_USE_TLS = True

# Structured logs with the correlation ID on every record, so one failed checkout traces
# end to end. Vercel keeps an hour of them on Hobby; Sentry carries the history.
LOGGING["handlers"]["console"]["formatter"] = "json"  # noqa: F405

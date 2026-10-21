"""Test settings: fast hashers, in-memory email, and a faked payment gateway.

``RAZORPAY_FAKE_MODE`` lets the suite sign its own webhooks with the secret below and
run the real fulfilment path, with no Razorpay account and no network call.
"""

from jinja2 import StrictUndefined

from .base import *  # noqa: F403
from .base import TEMPLATES

DEBUG = False
ALLOWED_HOSTS = ["localhost", "127.0.0.1", "testserver"]

PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"

TEMPLATES[0]["OPTIONS"]["undefined"] = StrictUndefined

RAZORPAY_KEY_ID = "rzp_test_suite"
RAZORPAY_KEY_SECRET = "test-key-secret"
RAZORPAY_WEBHOOK_SECRET = "test-webhook-secret"
RAZORPAY_FAKE_MODE = True

#!/usr/bin/env bash
# Boots the Django storefront for the Playwright e2e suite: migrate, seed the catalogue and the
# dev users, then serve on 127.0.0.1:8000. USE_SQLITE pins a local sqlite file so the run never
# touches a real database, and RAZORPAY_FAKE_MODE lets checkout reach fulfilment without a
# Razorpay account (the suite signs its own webhook, exactly as the pytest suite does).
set -euo pipefail

cd "$(dirname "$0")/.."

export DJANGO_SETTINGS_MODULE=config.settings.local
export DJANGO_DEBUG=True
export USE_SQLITE=1
export RAZORPAY_FAKE_MODE=True
export RAZORPAY_WEBHOOK_SECRET=e2e-webhook-secret
export RAZORPAY_KEY_ID=rzp_test_e2e
# create_gateway_order refuses to run without a secret even in fake mode, so it needs a value.
export RAZORPAY_KEY_SECRET=e2e-insecure-secret
export DJANGO_SECRET_KEY=e2e-insecure-key

uv run python manage.py migrate --noinput
uv run python manage.py seed_catalog
uv run python manage.py seed_dev_users
exec uv run python manage.py runserver 127.0.0.1:8000 --noreload

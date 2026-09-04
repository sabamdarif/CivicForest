# CivicForest

Premium menswear storefront for the Indian market: INR pricing, GST invoicing, prepaid
only. **One Django project**, server-rendered with Jinja2, hand-written CSS and vanilla
ES modules, deployed as a single Vercel function. Postgres on Neon, files on Cloudflare
R2, deferred work as database job rows swept by cron endpoints.

No frontend framework, no bundler, no second host, no Redis, no Celery, no Docker in the
production path. Those are constraints, not omissions: see `CLAUDE.md`.

- Every settled decision, with IDs to cite: [`rebuild/01-decisions.md`](./rebuild/01-decisions.md)
- Verified platform, vendor and legal facts: [`rebuild/02-research.md`](./rebuild/02-research.md)
- Target architecture: [`rebuild/03-architecture.md`](./rebuild/03-architecture.md)
- Milestones and acceptance criteria: [`rebuild/04-build-plan.md`](./rebuild/04-build-plan.md)

> **Status:** mid-rebuild. The proven money-path code carries over (server-side
> re-pricing, webhook idempotency, cart merge, upload sanitisation, the Qikink client)
> and 103 tests pass. Every page, template, stylesheet and script is being written from
> M1 onward, so `/` is a placeholder today. The previous Next.js stack is recoverable
> from the `v1-nextjs` tag.

---

## Contents

1. [Requirements](#1-requirements)
2. [Quick start](#2-quick-start)
3. [Environment variables](#3-environment-variables)
4. [API keys, and where to get them](#4-api-keys-and-where-to-get-them)
5. [Admin access](#5-admin-access)
6. [Checks and tests](#6-checks-and-tests)
7. [Project layout](#7-project-layout)
8. [Deployment](#8-deployment)
9. [Security notes](#9-security-notes)
10. [Troubleshooting](#10-troubleshooting)

---

## 1. Requirements

| Tool | Why |
|---|---|
| **Python 3.12** | the runtime, pinned by `requires-python` in `pyproject.toml` |
| **[uv](https://docs.astral.sh/uv/)** | dependency resolution, the virtualenv, and every command runner |
| _(for deployment)_ **[Vercel CLI](https://vercel.com/docs/cli) 50.38+** | `vercel dev` and `vercel env pull` |

Nothing else. No Docker, no Node, no Postgres server needed for local work.

## 2. Quick start

```bash
cp .env.example .env          # the shipped defaults run offline, with no API keys
uv sync --dev                 # creates .venv and installs everything

uv run python manage.py migrate
uv run python manage.py seed_catalog        # demo categories and products
uv run python manage.py createsuperuser     # optional, for the admin
uv run python manage.py runserver           # http://127.0.0.1:8000
```

`.env.example` sets `USE_SQLITE=1`, so this runs against `db.sqlite3` with no Postgres
and no credentials. Email prints to the console. Payments and Qikink are unconfigured and
their endpoints report that plainly rather than failing obscurely.

Search is the one feature SQLite cannot serve in full: ranking, prefix matching and typo
tolerance are Postgres, so on `USE_SQLITE=1` the query path degrades to substring matching over
the same document and `/search/` still answers. `seed_catalog` builds the search documents itself;
after editing the catalogue outside the admin, rebuild them with
`uv run python manage.py reindex_search` (`--stale` for only what changed).

To run the app the way Vercel will, once the project exists:

```bash
vercel env pull               # writes .env.local from the project settings
vercel dev
```

---

## 3. Environment variables

Everything is read from the environment through `django-environ`, in
`config/settings/base.py` and nowhere else. [`.env.example`](./.env.example) is the
documented template and lists every variable with a comment. `.env` is git-ignored.

| Group | Variables |
|---|---|
| Core | `DJANGO_SETTINGS_MODULE` `DJANGO_SECRET_KEY` `DJANGO_DEBUG` `DJANGO_ALLOWED_HOSTS` `CSRF_TRUSTED_ORIGINS` |
| Admin | `DJANGO_ADMIN_URL` `STAFF_SESSION_AGE` |
| Database | `DATABASE_URL` (Neon, pooled), `USE_SQLITE` |
| Object storage | `S3_ENDPOINT_URL` `S3_ACCESS_KEY_ID` `S3_SECRET_ACCESS_KEY` `S3_BUCKET_NAME` `S3_PRIVATE_BUCKET_NAME` `S3_REGION` `S3_SIGNED_URL_TTL` `R2_PUBLIC_BASE_URL` |
| Pricing | `SHIPPING_FLAT_RATE` `FREE_SHIPPING_THRESHOLD` `CURRENCY` |
| Payments | `RAZORPAY_KEY_ID` `RAZORPAY_KEY_SECRET` `RAZORPAY_WEBHOOK_SECRET` |
| Print | `QIKINK_CLIENT_ID` `QIKINK_CLIENT_SECRET` `QIKINK_BASE_URL` plus the four path overrides |
| Email | `RESEND_API_KEY` `DEFAULT_FROM_EMAIL` `SUPPORT_EMAIL`, or any `EMAIL_HOST` SMTP provider |
| Social login | `GOOGLE_OAUTH_CLIENT_ID` `GOOGLE_OAUTH_CLIENT_SECRET` |
| Observability | `HEALTH_CHECK_TOKEN` `SENTRY_DSN` `SENTRY_ENVIRONMENT` `SENTRY_TRACES_SAMPLE_RATE` |

Four settings modules, selected by `DJANGO_SETTINGS_MODULE`:

| Module | Used by | Differences |
|---|---|---|
| `config.settings.base` | nothing directly | every shared value; no security flag branches on `DEBUG` |
| `config.settings.local` | development | `DEBUG`, plain-HTTP cookies, console email, `StrictUndefined` templates |
| `config.settings.production` | Vercel | Neon, R2, Resend, HSTS, SSL redirect, Secure cookies, hashed static files, database cache |
| `config.settings.test` | pytest | fast hashers, in-memory email, faked Razorpay, `StrictUndefined` |

---

## 4. API keys, and where to get them

None are needed to run and test offline. Each one unlocks its own feature.

| Service | Variables | Where | Notes |
|---|---|---|---|
| **Neon** (Postgres) | `DATABASE_URL` | Neon console, project → Connection Details. Copy the **pooled** string | Branch per preview deployment. Free tier covers development |
| **Cloudflare R2** (files) | `S3_ENDPOINT_URL` `S3_ACCESS_KEY_ID` `S3_SECRET_ACCESS_KEY` `S3_BUCKET_NAME` `S3_PRIVATE_BUCKET_NAME` `R2_PUBLIC_BASE_URL` | Cloudflare dashboard → R2 → Manage R2 API Tokens. Endpoint is `https://<ACCOUNT_ID>.r2.cloudflarestorage.com` | Two buckets: product imagery public behind a CDN hostname, customer artwork private. Set `S3_REGION=auto` |
| **Razorpay** (payments) | `RAZORPAY_KEY_ID` `RAZORPAY_KEY_SECRET` `RAZORPAY_WEBHOOK_SECRET` | Dashboard → Settings → API Keys, and Settings → Webhooks for the separate webhook secret | Use Test mode keys in development. The webhook secret is what verifies incoming deliveries and is not the API secret |
| **Qikink** (custom print) | `QIKINK_CLIENT_ID` `QIKINK_CLIENT_SECRET` | Dashboard → Settings → Open API | Server-side only. The backend exchanges them for a token cached about an hour. `QIKINK_BASE_URL` defaults to the sandbox host, which has a **separate product database** from live |
| **Resend** (email) | `RESEND_API_KEY` | Resend → API Keys | Production sends over `smtp.resend.com` with `resend` as the username and the key as the password. SPF, DKIM and DMARC on the sending domain before launch |
| **Google** (social login) | `GOOGLE_OAUTH_CLIENT_ID` `GOOGLE_OAUTH_CLIENT_SECRET` | Google Cloud Console → APIs and Services → Credentials → OAuth client ID (Web application) | Add the site origin to authorised origins and the allauth callback to redirect URIs |
| **Sentry** (errors) | `SENTRY_DSN` | Sentry → Project → Settings → Client Keys | Optional but close to required in production: Vercel keeps one hour of runtime logs on Hobby |

In production these come from the Vercel project's environment variables, never from a
file in the repository.

---

## 5. Admin access

The Django admin sits at a non-guessable path from `DJANGO_ADMIN_URL`, never `/admin/`.
Leave that variable unset and the admin is served where nobody will find it.

Two gates, both in Django, so both apply under `runserver` too:

1. **Staff TOTP.** An authenticated staff user whose *session* did not complete an MFA
   step cannot view the admin. Enrolment alone is not enough, so a phished password on a
   non-MFA login path does not get in.
2. **Short staff sessions.** `STAFF_SESSION_AGE`, one hour by default, applies on every
   path, not just the admin.

Django's own admin login page is never served, because it authenticates with a password
alone and skips allauth's MFA step. Staff sign in through the site.

A first superuser therefore needs a TOTP authenticator before the admin opens. M5 adds a
real enrolment page; until then, from `uv run python manage.py shell`:

```python
from django.contrib.auth import get_user_model
from allauth.mfa.totp.internal.auth import TOTP, generate_totp_secret

user = get_user_model().objects.get(email="you@example.com")
secret = generate_totp_secret()
TOTP.activate(user, secret)
print("Add this secret to your authenticator app:", secret)
```

---

## 6. Checks and tests

One command runs everything that can run locally, cheapest failure first:

```bash
./check-before-commit.sh
```

That is the em dash grep on the staged diff, `ruff check`, `ruff format --check`,
`makemigrations --check --dry-run`, then `pytest -q`. Install the commit-message hook once
per clone so a bloated commit body is rejected:

```bash
ln -sf ../../hooks/commit-msg .git/hooks/commit-msg
```

Individual pieces:

```bash
USE_SQLITE=1 DJANGO_SECRET_KEY=dev-key uv run pytest -q
USE_SQLITE=1 DJANGO_SECRET_KEY=dev-key uv run pytest apps/cart/tests/test_cart.py
uv run ruff check apps/cart      # one app
uv run ruff format .             # write, not just check
uv run pip-audit --strict        # known advisories in the locked dependency set
```

Tests run on `config.settings.test`, which is SQLite unless `DATABASE_URL` is set. CI sets
it to a Postgres service so PG-specific behaviour is exercised, and also runs `ruff`,
`pip-audit` and CodeQL.

---

## 7. Project layout

```
CivicForest/
├── manage.py · pyproject.toml · uv.lock · check-before-commit.sh
├── config/
│   ├── settings/{base,local,production,test}.py
│   ├── urls.py · wsgi.py          # WSGI is the only entrypoint, deliberately
│   └── jinja2.py                  # the Jinja2 environment: globals and filters
├── apps/
│   ├── common/                    # base models, pagination, throttles, email, middleware
│   ├── accounts/ catalog/ cart/ orders/ payments/ custom_orders/ search/
│   └── …                          # each: models · services · serializers · views · admin · tests
├── templates/
│   ├── jinja2/                    # every page CivicForest owns
│   └── django/                    # allauth and admin overrides, which must be DTL
├── static/{css,js,icons,fonts,img}/
├── designs/                       # reference screenshots
└── rebuild/                       # the plan, and legacy/ for what it superseded
```

Dependency direction is one way: views call services, services call models. A view holding
business logic, or a model calling another app's service, is the thing to fix.

---

## 8. Deployment

Vercel detects the project from `manage.py`, resolves the entrypoint from
`WSGI_APPLICATION`, and turns the whole of Django into one function. `collectstatic` runs
automatically during the build and the CDN serves the result, so no build script is
needed. `[tool.vercel]` in `pyproject.toml` names the entrypoint explicitly anyway.

Set every variable from section 3 in the Vercel project, with
`DJANGO_SETTINGS_MODULE=config.settings.production`.

Release, with the migration step deliberately manual:

1. Push a branch. Vercel builds a preview against that Neon branch.
2. CI must be green, and the preview must look right.
3. `vercel env pull`, then `uv run python manage.py migrate` against production from a
   local shell. Migrations stay backward compatible, so the live function keeps working
   during the window. The search migration issues `CREATE EXTENSION pg_trgm`, so the
   database role needs the rights for it; on any other backend that operation is a no-op.
4. Promote the deployment.
5. Check `/healthz/`, place a Razorpay test order, read the jobs panel.

Rollback is promoting the previous deployment. Because migrations are additive and
backward compatible there is no database rollback, which is the whole reason for that
constraint.

One-off, after the first migrate on a new database:

```bash
uv run python manage.py createcachetable    # production uses the database cache
```

Platform limits that shape the code, verified in `rebuild/02-research.md` §1: request and
response bodies cap at **4.5 MB**, the filesystem is read-only except `/tmp`, and cron
jobs fire **once a day on Hobby** against once a minute on Pro.

---

## 9. Security notes

- Money is computed server-side, always. The client sends ids, quantities and a coupon
  code, never a price or a total.
- Uploads never pass through Django. Artwork goes browser to R2 with a short-lived
  presigned URL, and only the key is stored.
- Nothing reaches Qikink without a verified payment and a passed review, and every
  submission carries an idempotency key so a retry cannot create a second print job.
- Webhooks are HMAC-verified and deduplicated on a `(gateway, event_id)` ledger. The
  webhook, not the browser callback, is the authoritative confirmation.
- Argon2id hashing, email-only login with UUID primary keys, session plus CSRF auth with
  no CORS, explicit serializer fields, ownership-scoped querysets, per-endpoint throttles.
- Customer artwork lives in a private bucket under random UUID filenames and is served
  only through signed URLs.
- Consent boxes default to unticked and every charge is visible before commitment. India's
  dark-pattern guidelines carry a first-violation penalty of ten lakh rupees, so this is
  law rather than taste.

---

## 10. Troubleshooting

| Symptom | Fix |
|---|---|
| `ImproperlyConfigured: Set the DJANGO_SECRET_KEY environment variable` | No `.env` yet, or the variable is missing from it. There is deliberately no default |
| Admin returns 404 | `DJANGO_ADMIN_URL` is unset, or the staff user's session never completed an MFA step. See section 5 |
| Redirected away from the admin after logging in | Staff TOTP is not enrolled. Bootstrap it with the shell snippet in section 5 |
| Storefront shows no products | `uv run python manage.py migrate && uv run python manage.py seed_catalog` |
| `Missing staticfiles manifest entry` | Production settings hash static filenames. Run `collectstatic`, or use `config.settings.local` |
| Tests try to reach a real database | `DATABASE_URL` is set in `.env`. Prefix the command with `USE_SQLITE=1` |
| A template renders nothing where a value should be | Local and test settings use `StrictUndefined`, so it raises instead. Read the traceback for the variable name |
| `413` from a deployed upload | Vercel caps request bodies at 4.5 MB. Anything larger must go straight to R2 |





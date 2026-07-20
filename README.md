# CivicForest

Premium clothing storefront — **Django 5.2 + DRF** API and a **Next.js (App Router)**
frontend, behind a **Caddy** reverse proxy with local HTTPS. Data is **PostgreSQL 17**,
**Redis**, and **Meilisearch**; async work runs on **Celery**.

- Full architecture & rationale → [`plan.md`](./plan.md)
- Execution plan → [`implementation_plan.md`](./implementation_plan.md)
- Progress / what's done vs left → [`tasks.md`](./tasks.md)

> **Status:** the whole purchase path is built and verified end-to-end — accounts/auth,
> catalog, storefront, search (with a Postgres fallback), **cart/wishlist/coupons,
> orders, Razorpay payments, and Qikink print fulfilment**, plus admin hardening,
> CI (tests/audits/Trivy), and observability. Test breadth (Playwright E2E, k6 load,
> axe a11y) is in place. What's left is non-code: live credentials and repo/monitoring
> settings (see `tasks.md`).

---

## Table of contents

1. [Architecture at a glance](#1-architecture-at-a-glance)
2. [Prerequisites](#2-prerequisites)
3. [Quick start (Docker)](#3-quick-start-docker)
4. [Local HTTPS setup (mkcert)](#4-local-https-setup-mkcert)
5. [Environment variables](#5-environment-variables)
6. [API keys — what you need and where to get them](#6-api-keys--what-you-need-and-where-to-get-them)
7. [Make commands](#7-make-commands)
8. [Running pieces without Docker](#8-running-pieces-without-docker)
9. [Accessing the admin panel](#9-accessing-the-admin-panel)
10. [Testing](#10-testing)
11. [Project layout](#11-project-layout)
12. [Deployment](#12-deployment)
13. [Security notes](#13-security-notes)
14. [Troubleshooting](#14-troubleshooting)

---

## 1. Architecture at a glance

```
Browser ──► Caddy (TLS terminate)
              ├─ civicforest.local       ──► Next.js  (frontend:3000)
              └─ api.civicforest.local   ──► Django   (backend:8000)
                                                │
                        ┌───────────────────────┼───────────────────────┐
                     Postgres                  Redis                 Meilisearch
                  (catalog/users)     (cache · Celery broker ·        (search index;
                                        throttle store)             Postgres fallback)
                                                │
                                     Celery worker + beat  (index sync, print fulfilment, order emails)
```

Two deployable app units (`backend`, `frontend`) plus supporting services, all in
`docker-compose.yml`. The same Caddy proxy is used in dev and prod for real parity.

---

## 2. Prerequisites

| Tool | Why | Install |
|------|-----|---------|
| **Docker + Docker Compose** | runs the whole stack | <https://docs.docker.com/get-docker/> |
| **mkcert** | browser-trusted local HTTPS certs | <https://github.com/FiloSottile/mkcert#installation> |
| *(optional)* **uv** | run/lint backend without Docker | <https://docs.astral.sh/uv/> |
| *(optional)* **Node 22+** | run frontend without Docker | <https://nodejs.org/> |

You do **not** need Python/Node installed to run via Docker — only Docker + mkcert.

---

## 3. Quick start (Docker)

```bash
# 1. Configure environment
cp .env.example .env            # dev defaults work out of the box

# 2. Trust a local CA and issue certs for the .local hostnames
make certs

# 3. Map the hostnames to localhost (one-time)
echo "127.0.0.1 civicforest.local api.civicforest.local" | sudo tee -a /etc/hosts

# 4. Build & start everything
make up

# 5. Set up the database + demo data
make migrate
make seed                       # 5 categories + 13 demo products (brand photos)
make reindex                    # push catalog into Meilisearch
make createsuperuser            # optional, for the admin
```

Open:

| URL | What |
|-----|------|
| <https://civicforest.local> | Storefront |
| <https://api.civicforest.local/api/v1/> | API root |
| <https://api.civicforest.local/api/docs/> | Swagger docs (dev only) |
| `https://api.civicforest.local/<DJANGO_ADMIN_URL>` | Admin — path from `.env`, **not** `/admin/`; needs MFA (see [§9](#9-accessing-the-admin-panel)) |

Stop with `make down`. Tail logs with `make logs`.

---

## 4. Local HTTPS setup (mkcert)

HTTPS is on in **dev and prod alike**, so cookie `Secure`/HSTS/CSP behave identically
everywhere (no `if DEBUG` branching around security). `make certs` runs:

```bash
mkcert -install                 # trust a local CA in your OS/browser (one-time)
cd caddy/certs
mkcert civicforest.local
mkcert api.civicforest.local
```

This produces `caddy/certs/*.pem` (git-ignored), which Caddy mounts. If browsers still
warn, restart the browser after `mkcert -install`, and confirm the `/etc/hosts` entry
from step 3 exists.

---

## 5. Environment variables

All config is read from the environment — see [`.env.example`](./.env.example) for the
documented template. `.env` is git-ignored; **never commit real secrets.** Key groups:

| Group | Keys | Notes |
|-------|------|-------|
| Core | `DJANGO_SECRET_KEY`, `DJANGO_DEBUG`, `DJANGO_ALLOWED_HOSTS`, `DJANGO_ADMIN_URL` | `ADMIN_URL` is a random path, never `/admin/` |
| Frontend/CORS | `FRONTEND_ORIGIN`, `CORS_ALLOWED_ORIGINS`, `CSRF_TRUSTED_ORIGINS`, `SESSION_COOKIE_DOMAIN` | explicit allow-lists (cookies are involved) |
| API URLs | `NEXT_PUBLIC_API_BASE_URL`, `INTERNAL_API_BASE_URL` | public vs in-network SSR base |
| Postgres | `POSTGRES_*`, `DATABASE_URL` | |
| Redis | `REDIS_URL`, `CELERY_BROKER_URL`, `CELERY_RESULT_BACKEND` | |
| Meilisearch | `MEILISEARCH_URL`, `MEILISEARCH_MASTER_KEY` | |
| Object storage | `S3_*` | for uploads/media (deferred) |
| Payments | `RAZORPAY_*` | deferred; see below |
| Print | `QIKINK_CLIENT_ID`, `QIKINK_CLIENT_SECRET`, `QIKINK_BASE_URL` | Qikink Open API |
| Social login | `GOOGLE_OAUTH_*`, `APPLE_OAUTH_*` | UI built, keys optional |

For local dev the committed defaults are sufficient — **no external API keys are
required to run the current foundation.**

---

## 6. API keys — what you need and where to get them

None are needed to run and test the stack offline (checkout uses fake/test modes). You
need these to exercise the real payment/fulfilment/upload paths and to go live. Get and
store each as an environment variable.

### Required for their feature

| Service | Env vars | Where to get it | Notes |
|---------|----------|-----------------|-------|
| **Razorpay** (payments) | `RAZORPAY_KEY_ID`, `RAZORPAY_KEY_SECRET`, `RAZORPAY_WEBHOOK_SECRET` | Razorpay Dashboard → **Settings → API Keys** (generate key/secret). Webhook secret: **Settings → Webhooks → Add webhook** (you set the secret there). <https://dashboard.razorpay.com/> | Use **Test mode** keys for dev. The webhook secret is separate from the API secret and is what verifies incoming webhooks. |
| **Qikink** (custom-print fulfilment) | `QIKINK_CLIENT_ID`, `QIKINK_CLIENT_SECRET` (base URL/paths overridable via `QIKINK_BASE_URL`, `QIKINK_TOKEN_PATH`, `QIKINK_ORDER_CREATE_PATH`, `QIKINK_ORDER_STATUS_PATH`) | Qikink Dashboard → **Settings → API / Open API** for the ClientId + client secret. Reference: Qikink Open API Postman docs. <https://qikink.com/> | Server-side only — the backend exchanges these for a short-lived token (cached ~1h) and calls Qikink; never expose to the browser. Defaults point at the sandbox host; set `QIKINK_BASE_URL` to production when going live. |
| **Cloudflare R2** *(or AWS S3)* (media/uploads) | `S3_ENDPOINT_URL`, `S3_ACCESS_KEY_ID`, `S3_SECRET_ACCESS_KEY`, `S3_BUCKET_NAME`, `S3_REGION` | R2: Cloudflare Dashboard → **R2 → Manage R2 API Tokens** (<https://dash.cloudflare.com/>). S3: AWS IAM → **Users → Security credentials → Access keys**, plus an S3 bucket. | R2 is S3-compatible; set `S3_ENDPOINT_URL` to your R2 endpoint. |

### Optional (social login — the UI exists, keys just enable it)

| Provider | Env vars | Where to get it |
|----------|----------|-----------------|
| **Google** | `GOOGLE_OAUTH_CLIENT_ID`, `GOOGLE_OAUTH_CLIENT_SECRET` | Google Cloud Console → **APIs & Services → Credentials → Create OAuth client ID** (Web application). Add `https://api.civicforest.local` to authorized origins and the allauth callback to redirect URIs. <https://console.cloud.google.com/apis/credentials> |
| **Apple** | `APPLE_OAUTH_CLIENT_ID`, `APPLE_OAUTH_SECRET` | Apple Developer → **Certificates, Identifiers & Profiles → Identifiers** (Services ID) + a Sign in with Apple key. <https://developer.apple.com/account/resources/> |

### Nice to have (production)

| Service | Env var(s) | Where |
|---------|-----------|-------|
| **Sentry** (error tracking) | `SENTRY_DSN` | Sentry → **Project → Settings → Client Keys (DSN)**. <https://sentry.io/> |

> **Handling secrets:** in production, inject these from a secrets manager
> (Doppler / Vault / your cloud provider's secret store), not a checked-in file.
> Rotate periodically. See `plan.md` §12.

---

## 7. Make commands

Run `make help` to list them. Highlights:

| Command | Does |
|---------|------|
| `make certs` | Trust local CA + issue mkcert certs for the `.local` hosts |
| `make up` | Build & start the full stack (detached) |
| `make down` | Stop the stack |
| `make logs` | Tail all container logs |
| `make migrate` | Apply database migrations |
| `make makemigrations` | Create new migrations |
| `make seed` | Seed categories + demo catalog (idempotent) |
| `make reindex` | Rebuild the Meilisearch index from Postgres |
| `make createsuperuser` | Create a Django admin superuser |
| `make shell` | Django shell |
| `make test` | Run backend tests (pytest) |
| `make lint` | Lint backend (ruff) + frontend (eslint) |
| `make fmt` | Auto-format the backend (ruff) |

---

## 8. Running pieces without Docker

Useful for fast iteration or CI.

**Backend** (SQLite, no Postgres/Redis/Meili needed — search uses the Postgres/SQLite
fallback and Celery runs eagerly):

```bash
cd backend
uv sync --dev
export USE_SQLITE=1 DJANGO_SECRET_KEY=dev-key
uv run python manage.py migrate
uv run python manage.py seed_catalog
uv run python manage.py runserver      # http://127.0.0.1:8000
uv run pytest                          # tests
uv run ruff check . && uv run ruff format --check .
```

**Frontend:**

```bash
cd frontend
npm install
npm run dev            # http://localhost:3000
npm run build          # production build
npm run typecheck      # tsc --noEmit
npm run lint
```

> When running the frontend standalone against a non-Docker backend, point
> `NEXT_PUBLIC_API_BASE_URL` / `INTERNAL_API_BASE_URL` at `http://127.0.0.1:8000`.

---

## 9. Accessing the admin panel

The Django admin is deliberately hard to reach — it lives at a **non-guessable path**
(never `/admin/`) and sits behind **two independent gates**:

1. **Caddy IP allow-list** — requests to the admin path from an IP not in
   `ADMIN_IP_ALLOWLIST` (default `127.0.0.1/32`) get a generic **404** before the
   request ever touches Django, so the panel's existence isn't leaked.
2. **Staff TOTP MFA** (`StaffAdminMiddleware`) — an authenticated staff user without a
   confirmed TOTP authenticator can't view the admin. Staff sessions also expire faster
   (`STAFF_SESSION_AGE`, default 1h).

**The URL** is `DJANGO_ADMIN_URL` from your `.env` (the shipped default is
`admin-4f2a9c/`). Full address in the Docker setup:

```
https://api.civicforest.local/admin-4f2a9c/        # ← replace with your DJANGO_ADMIN_URL
```

> `DJANGO_ADMIN_URL` (Django) and `DJANGO_ADMIN_PATH` (the Caddy matcher) must stay in
> sync — same path, `DJANGO_ADMIN_PATH` just has leading/trailing slashes. Change both
> to something private before going live.

### First-time access (create a superuser + enable MFA)

```bash
make createsuperuser          # or: uv run python manage.py createsuperuser (no Docker)
```

Because MFA is mandatory, a brand-new superuser is redirected to set up TOTP rather than
shown the admin. There's no standalone MFA-setup page yet, so **bootstrap the first
authenticator from the shell** (`make shell`, or `uv run python manage.py shell`):

```python
from django.contrib.auth import get_user_model
from allauth.mfa.totp.internal.auth import generate_totp_secret, TOTP

user = get_user_model().objects.get(email="you@example.com")
secret = generate_totp_secret()
TOTP.activate(user, secret)
print("Add this secret to your authenticator app:", secret)
```

Enter that Base32 secret into an authenticator app (Google Authenticator, Aegis, 1Password,
etc.) as a manual/"enter a setup key" entry. Then log in at the admin URL with your email,
password, and the rolling 6-digit code.

> **Running without Docker** (`runserver`, no Caddy): only the TOTP gate applies — the
> IP allow-list is a Caddy feature, so it isn't enforced. The admin URL is
> `http://127.0.0.1:8000/<DJANGO_ADMIN_URL>`.

---

## 10. Testing

| Layer | Command | Notes |
|-------|---------|-------|
| **Backend unit** | `make test` — or offline: `cd backend && USE_SQLITE=1 DJANGO_SECRET_KEY=dev-key uv run pytest` | 72 tests across accounts/catalog/cart/orders/payments/custom_orders |
| **Backend lint/format** | `make lint` · `cd backend && uv run ruff check . && uv run ruff format --check .` | |
| **Frontend typecheck/lint** | `cd frontend && npm run typecheck && npm run lint` | `tsc --noEmit` + eslint |
| **E2E (Playwright)** | `cd frontend && npm run e2e` | boots both servers itself |
| **Load (k6)** | `k6 run k6-search-suggest.js` | needs the API running + [k6](https://k6.io/docs/get-started/installation/) |
| **A11y (axe)** | `node frontend/axe-audit.js` | needs the storefront running + system Chrome |

### E2E details

`npm run e2e` starts everything on its own — no Docker needed. It runs Django on
`config.settings.e2e` (SQLite, fake Razorpay, a known webhook secret) at
`http://localhost:8001` and Next.js at `http://localhost:3001`, then drives system
Chrome through three critical paths:

- **auth** — signup → login
- **checkout** — search → cart → checkout, then a genuinely **HMAC-signed webhook** that
  runs the real fulfilment path (stock decrement, order transition)
- **custom-design** — upload flow for custom-print orders

```bash
cd frontend
npm install                    # first time: installs @playwright/test, puppeteer, axe
npm run e2e
```

> The E2E backend uses `RAZORPAY_FAKE_MODE=True`, so no Razorpay account or network call
> is needed — the webhook is signed locally with the test secret in `config/settings/e2e.py`.
> The Next.js server runs with `--no-turbo` to avoid a stale Turbopack lockfile; if you
> hit a `.next/dev` permission error from a past Docker run, clear it with
> `sudo rm -rf frontend/.next/dev`.

### Load + a11y details

```bash
# Load: hammer the suggestion endpoint (ramps to 50 VUs; p95<500ms, <5% errors).
# API_URL defaults to http://localhost:8000.
k6 run k6-search-suggest.js
API_URL=http://api.civicforest.local k6 run k6-search-suggest.js   # against Docker

# A11y: axe pass over 6 key pages. WEB_URL defaults to http://localhost:3000.
node frontend/axe-audit.js
```

---

## 11. Project layout

```
CivicForest/
├── plan.md · implementation_plan.md · tasks.md
├── docker-compose.yml · Makefile · .env.example
├── caddy/Caddyfile
├── .github/workflows/ci.yml
├── backend/                     # Django + DRF (uv-managed)
│   ├── config/settings/{base,local,production,e2e}.py
│   └── apps/{common,accounts,catalog,search,cart,orders,payments,custom_orders}/
│       └── models · services · serializers · views · admin · tests
├── frontend/                    # Next.js App Router + TS + Tailwind
│   ├── app/(storefront)/        # home, collections, shop, product, search, cart, checkout, about, contact
│   ├── app/(account)/           # login, signup, account, orders, wishlist
│   ├── components/{brand,layout,product,search,shop,account,ui}/
│   ├── lib/{api,auth,search,brand}/
│   ├── e2e/                     # Playwright specs (auth, checkout, custom-design) + helpers
│   └── axe-audit.js · playwright.config.ts
└── k6-search-suggest.js         # load test for the suggestion endpoint
```

---

## 12. Deployment

The same Docker images and Caddy config run in production; the differences are all
environment-driven.

1. **Settings:** set `DJANGO_SETTINGS_MODULE=config.settings.production`. This forces
   `DEBUG=False`, requires a real `DJANGO_SECRET_KEY`, and enables `SECURE_SSL_REDIRECT`
   + HSTS.
2. **Managed data services:** use a managed **PostgreSQL 17** (automated backups + PITR)
   and managed **Redis**; run **Meilisearch** as a service. Point `DATABASE_URL`,
   `REDIS_URL`, and `MEILISEARCH_URL` at them.
3. **Secrets:** inject all keys from §6 via your platform's secret store (not a file).
4. **TLS:** in production drop the `tls` lines from `caddy/Caddyfile` so Caddy
   auto-provisions real certificates via ACME for your public domains
   (`civicforest.com`, `api.civicforest.com`).
5. **Static files:** `python manage.py collectstatic` (served by WhiteNoise). Product
   media should live in **object storage** (R2/S3), not the container disk.
6. **Release step:** run `python manage.py migrate` as an explicit pre-traffic step;
   keep migrations backward-compatible so rollbacks are safe.
7. **Processes:** run `backend` (gunicorn + Uvicorn workers), `worker` (Celery), and
   `beat` (Celery beat) as separate services; `frontend` as the Next.js standalone
   server.
8. **CI/CD (planned, `plan.md` §14):** lint → typecheck → test → build images → Trivy
   scan → push → migrate → deploy, with CodeQL + Dependabot + secret scanning and
   branch protection on `main`.

---

## 13. Security notes

- HTTPS everywhere (dev + prod) → identical cookie `Secure`/HSTS/CSP config.
- Admin at a **non-guessable env-driven path**, never `/admin/`; MFA-ready via allauth.
- Argon2id password hashing; email-based custom user with **UUID** primary keys.
- DRF **session-cookie** auth + CSRF enforced; explicit CORS/CSRF allow-lists.
- **Explicit serializer fields** (never `__all__`); price/stock are read-only outputs.
- Per-endpoint **throttles** (tighter on auth + search); hard **max page size**.
- Ownership-scoped querysets (no IDOR); consistent error envelope.

Full checklist: `plan.md` §12.

---

## 14. Troubleshooting

| Symptom | Fix |
|---------|-----|
| Browser TLS warning on `*.local` | Re-run `make certs`, restart the browser, verify `/etc/hosts` entry. |
| `civicforest.local` won't resolve | Add `127.0.0.1 civicforest.local api.civicforest.local` to `/etc/hosts`. |
| Storefront shows no products | Run `make migrate && make seed` (and `make reindex` for search). |
| Search returns nothing | Meili not indexed → `make reindex`. Search still works via the Postgres fallback. |
| API returns 403 on writes | CSRF — the frontend must send `X-CSRFToken`; hit any GET first to receive the cookie. |
| Backend won't boot without Postgres | Use `USE_SQLITE=1` for offline runs (see §8). |
| Admin URL returns **404** | Expected for non-allow-listed IPs. Confirm your IP is in `ADMIN_IP_ALLOWLIST`, and that `DJANGO_ADMIN_URL`/`DJANGO_ADMIN_PATH` match (see §9). |
| Redirected away from admin after login | Staff MFA isn't set up — bootstrap a TOTP authenticator (§9). |
| E2E fails with a `.next/dev` permission error | Root-owned dir from a past Docker run → `sudo rm -rf frontend/.next/dev`. |

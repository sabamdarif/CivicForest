# CivicForest

Premium clothing storefront — **Django 5.2 + DRF** API and a **Next.js (App Router)**
frontend, behind a **Caddy** reverse proxy with local HTTPS. Data is **PostgreSQL 17**,
**Redis**, and **Meilisearch**; async work runs on **Celery**.

- Full architecture & rationale → [`plan.md`](./plan.md)
- Execution plan → [`implementation_plan.md`](./implementation_plan.md)
- Progress / what's done vs left → [`tasks.md`](./tasks.md)

> **Status:** the foundation slice is complete and verified — accounts/auth, catalog,
> storefront (Home, Collections, Shop, Product, Search, About, Contact, Login), and
> search with a Postgres fallback. Cart, orders, payments, and print fulfilment are
> scoped but not yet built (see `tasks.md`).

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
9. [Project layout](#9-project-layout)
10. [Deployment](#10-deployment)
11. [Security notes](#11-security-notes)
12. [Troubleshooting](#12-troubleshooting)

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
                                     Celery worker + beat  (index sync, later: payments/print/email)
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
| `https://api.civicforest.local/<DJANGO_ADMIN_URL>` | Admin (path from `.env`, **not** `/admin/`) |

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
| Print | `PRINT_PROVIDER`, `PRINT_PROVIDER_API_TOKEN` | deferred |
| Social login | `GOOGLE_OAUTH_*`, `APPLE_OAUTH_*` | UI built, keys optional |

For local dev the committed defaults are sufficient — **no external API keys are
required to run the current foundation.**

---

## 6. API keys — what you need and where to get them

None are needed for the foundation slice. You'll need these as later phases land
(cart → checkout → fulfilment). Get and store each as an environment variable.

### Required for their feature

| Service | Env vars | Where to get it | Notes |
|---------|----------|-----------------|-------|
| **Razorpay** (payments) | `RAZORPAY_KEY_ID`, `RAZORPAY_KEY_SECRET`, `RAZORPAY_WEBHOOK_SECRET` | Razorpay Dashboard → **Settings → API Keys** (generate key/secret). Webhook secret: **Settings → Webhooks → Add webhook** (you set the secret there). <https://dashboard.razorpay.com/> | Use **Test mode** keys for dev. The webhook secret is separate from the API secret and is what verifies incoming webhooks. |
| **Printful** *(or Printify)* (print fulfilment) | `PRINT_PROVIDER_API_TOKEN` (`PRINT_PROVIDER=printful`) | Printful → **Settings → Developers → API Tokens** (<https://developers.printful.com/>). Printify → **My Profile → Connections → Generate token** (<https://printify.com/app/account/api>). | Store-scoped token. Never expose it to the browser — the backend calls the provider. |
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

## 9. Project layout

```
CivicForest/
├── plan.md · implementation_plan.md · tasks.md
├── docker-compose.yml · Makefile · .env.example
├── caddy/Caddyfile
├── .github/workflows/ci.yml
├── backend/                     # Django + DRF (uv-managed)
│   ├── config/settings/{base,local,production}.py
│   └── apps/{common,accounts,catalog,search}/
│       └── models · services · serializers · views · admin · tests
└── frontend/                    # Next.js App Router + TS + Tailwind
    ├── app/(storefront)/        # home, collections, shop, product, search, about, contact
    ├── app/(account)/           # login, account
    ├── components/{brand,layout,product,search,shop,account,ui}/
    └── lib/{api,auth,search,brand}/
```

---

## 10. Deployment

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

## 11. Security notes

- HTTPS everywhere (dev + prod) → identical cookie `Secure`/HSTS/CSP config.
- Admin at a **non-guessable env-driven path**, never `/admin/`; MFA-ready via allauth.
- Argon2id password hashing; email-based custom user with **UUID** primary keys.
- DRF **session-cookie** auth + CSRF enforced; explicit CORS/CSRF allow-lists.
- **Explicit serializer fields** (never `__all__`); price/stock are read-only outputs.
- Per-endpoint **throttles** (tighter on auth + search); hard **max page size**.
- Ownership-scoped querysets (no IDOR); consistent error envelope.

Full checklist: `plan.md` §12.

---

## 12. Troubleshooting

| Symptom | Fix |
|---------|-----|
| Browser TLS warning on `*.local` | Re-run `make certs`, restart the browser, verify `/etc/hosts` entry. |
| `civicforest.local` won't resolve | Add `127.0.0.1 civicforest.local api.civicforest.local` to `/etc/hosts`. |
| Storefront shows no products | Run `make migrate && make seed` (and `make reindex` for search). |
| Search returns nothing | Meili not indexed → `make reindex`. Search still works via the Postgres fallback. |
| API returns 403 on writes | CSRF — the frontend must send `X-CSRFToken`; hit any GET first to receive the cookie. |
| Backend won't boot without Postgres | Use `USE_SQLITE=1` for offline runs (see §8). |

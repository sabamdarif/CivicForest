# CivicForest — Task Checklist

Progress tracker for the foundation slice (phases 1–5). Companion to
[`implementation_plan.md`](./implementation_plan.md). Checked as work lands.

Legend: `[ ]` todo · `[~]` in progress · `[x]` done · `[-]` deferred

---

## 📊 Progress summary

**Foundation slice: ✅ complete and verified.** Phases 1–5 built, runnable end-to-end.

| Area | Status |
|------|--------|
| Phase 0 — Planning docs | ✅ Done |
| Phase 1 — Scaffold, Docker, local HTTPS, CI | ✅ Done |
| Phase 2 — accounts + allauth headless + login | ✅ Done |
| Phase 3 — catalog + admin + seed | ✅ Done |
| Phase 4 — storefront pages | ✅ Done |
| Phase 5 — search (suggest + results + fallback) | ✅ Done |
| Verification (backend + frontend) | ✅ Done |
| Phases 6–12 (cart→launch) | ⏳ Deferred (scoped below) |

**Verification results (this machine):**
- `ruff check` → all checks passed · `ruff format --check` → clean
- `manage.py check` → 0 issues · `makemigrations --check` → no drift
- `pytest` → **7 passed** (accounts + catalog API, incl. IDOR/pagination-cap cases)
- Frontend `tsc --noEmit` → clean · `next build` → **11 routes built** ✅

**What's roughly "done" vs "left" for the whole product:**
Roughly **~40%** of the end-to-end store is in place (infra + auth + catalog +
storefront + search). The remaining **~60%** is commerce depth (cart, orders,
payments, custom-print), production hardening (CI security, observability), and
test breadth — all itemised under *Deferred* below.

---

## Phase 0 — Planning
- [x] Read `plan.md`, `designs/`, `images/`
- [x] Write `implementation_plan.md`
- [x] Write `tasks.md`

## Phase 1 — Scaffold + Docker + local HTTPS + CI
- [x] Monorepo dirs, root `.gitignore`, `.editorconfig`
- [x] `.env.example` (documented)
- [x] `backend/` Python project (uv, pyproject, ruff) + settings split + config
- [x] `frontend/` Next.js + TS + Tailwind theme + brand fonts + cF monogram
- [x] `docker-compose.yml` (postgres, redis, meilisearch, backend, worker, beat, frontend, caddy)
- [x] `caddy/Caddyfile` with TLS + routing
- [x] `Makefile` (up/down/migrate/seed/test/lint/certs)
- [x] `.github/workflows/ci.yml` (lint)
- [x] `README.md` (full setup / docker / make / deploy / API keys)

## Phase 2 — accounts + auth
- [x] `common` app: base model, pagination, exception handler
- [x] Custom `User` (UUID, email login) + `Address`
- [x] Argon2id + password validators + security settings
- [x] django-allauth headless config + DRF session/CSRF + throttles
- [x] `accounts` serializers/views (me, addresses) — ownership-scoped
- [x] Next.js `/login` page matching mockup (+ `/account` landing, logout)
- [x] `lib/auth` allauth headless client (session/login/logout/social)

## Phase 3 — catalog
- [x] Models: Material, Category, Tag, Product, ProductVariant, ProductImage
- [x] `services.py` (active querysets, price resolution) + `filters.py`
- [x] Serializers (list/detail, explicit fields, price/stock read-only)
- [x] Read-only viewsets + URLs (`/api/v1/catalog/...`, slash-optional)
- [x] Hardened admin (env path, editable catalog, inlines)
- [x] `seed_catalog` command (5 categories + 13 demo products using brand photos)

## Phase 4 — storefront
- [x] Design tokens + Tailwind theme + fonts + cF monogram
- [x] Layout: announcement bar, sticky nav, footer
- [x] `lib/api` typed catalog client (+ SSR ISR + graceful fallback)
- [x] Home page (hero, feature strip, category grid, Just Landed, values)
- [x] Collections page
- [x] Shop page (filters + grid + "Showing X–Y of N" + pagination + sort)
- [x] Product detail page (gallery + variant pickers + SEO metadata)
- [x] About + Contact pages (static, from mockups, incl. FAQ accordion)

## Phase 5 — search
- [x] `search` app: Meili index def + signals + Celery upsert/reindex tasks
- [x] Suggestion + full-search endpoints (minimal payload) + Postgres fallback
- [x] `useSearchSuggestions` hook (debounce/abort/min-len/LRU cache)
- [x] Search overlay in nav (keyboard nav + stale-response guard)
- [x] Full search results page matching mockup

## Verification
- [x] `manage.py check` + migrations clean (no drift)
- [x] `pytest` passing (7 tests)
- [x] `ruff` lint + format clean
- [x] Frontend `tsc` + `next build` clean
- [x] Update this file + plan with honest run status

---

## Deferred (later sessions) — the remaining ~60%

Nothing here is silently dropped — each maps to a `plan.md` section.

### Phase 6 — cart / wishlist (plan.md §4, §6)
- [-] Server-side Cart/CartItem (guest session + user merge on login)
- [-] Wishlist persistence (currently heart toggle is UI-only)
- [-] Coupon model + server-only validation at checkout

### Phase 7 — orders + payments (plan.md §9)
- [-] Order/OrderItem + state machine + server-recomputed totals + invoices
- [-] Razorpay order creation (server-to-server)
- [-] Webhook: raw-body HMAC verify, idempotency/event dedup, stock decrement w/ row locks

### Phase 8 — custom design orders (plan.md §8)
- [-] Upload → content-sniff MIME + re-encode/strip EXIF → private storage + signed URLs
- [-] Post-payment Celery call to Printful/Printify with idempotency key
- [-] Print-partner webhook → order status → customer email; "flagged for review" state

### Phase 9 — admin hardening (plan.md §11)
- [-] IP allow-list / Zero-Trust in front of the admin path
- [-] Require TOTP MFA for all staff; shorter staff session timeout
- [-] `django-auditlog` before/after field diffs

### Phase 10 — CI/CD & security scanning (plan.md §14)
- [-] CodeQL default setup, Dependabot, secret scanning + push protection
- [-] Trivy image scan; type-check + test stages; branch protection on `main`

### Phase 11 — observability (plan.md §16)
- [-] Sentry (Django + Next.js); `/healthz` `/readyz`; structured JSON logs + correlation IDs
- [-] Alerts on webhook-verify failures, Celery failure rate, payment/order mismatch

### Phase 12 — testing & launch (plan.md §15, §12)
- [-] Full pytest coverage (payments/webhook/search-sync), factory_boy fixtures
- [-] Playwright E2E (signup→login, search→cart→checkout, custom upload)
- [-] k6 load test on the suggestion endpoint; axe accessibility pass
- [-] Full security-checklist pass, restore-test the DB backups

### Cross-cutting
- [-] Social-login provider credentials (Google/Apple) — UI built, keys env-gated
- [-] Object storage (R2/S3) wired for product/media instead of local disk
- [-] signup + password-reset UI (login is built; endpoints exist via allauth)

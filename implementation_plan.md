# CivicForest — Implementation Plan

A cleaner, execution-focused companion to [`plan.md`](./plan.md). `plan.md` is the
full architectural rationale (18 sections). This document is the *how* and *in what
order* — the living plan we update as work lands. Progress lives in [`tasks.md`](./tasks.md).

CivicForest is a premium India-based clothing store. Brand: deep charcoal + warm
gold, serif display type, the "cF" leaf monogram. See `designs/` for the reference
mockups and `images/` for brand photography.

> **Status (foundation slice — phases 1–5): ✅ complete & verified.**
> Backend `ruff`/`check`/`migrations` clean, **7 pytest passing**; frontend `tsc`
> clean and `next build` green (11 routes). Phases 6–12 are scoped in
> [`tasks.md`](./tasks.md) and deferred. Run instructions in [`README.md`](./README.md).

---

## Guiding principles (from plan.md, kept front-of-mind)

- **Fat services, thin views.** Business logic lives in `services.py`, callable from
  viewsets, admin actions, and Celery tasks alike.
- **Never trust the client** for price, stock, totals, order state, permissions, or
  file validation. Those are server-side, always.
- **Explicit serializer fields.** Never `fields = "__all__"` on a writable serializer;
  read vs. write serializers split wherever a field must not be client-writable.
- **HTTPS everywhere, dev included** — so cookie `Secure`/HSTS/CSP are configured
  identically in every environment (no `if DEBUG` branching around security).
- **UUID primary keys** for anything a customer sees in a URL.
- **Comments only where the *why* isn't obvious.**

---

## Target architecture (foundation slice)

Monorepo, two top-level apps behind one reverse proxy:

```
Caddy (TLS)  ─┬─  /            → Next.js  (storefront SSR + client account pages)
              └─  /api /_allauth /media /admin → Django (DRF + allauth headless)

Django ── Postgres (catalog, users, orders)
      ├── Redis (cache, Celery broker, throttle store)
      └── Meilisearch (search index; Postgres icontains fallback)
Celery worker + beat ── async jobs (search reindex, later: payments/print/email)
```

Local hostnames: `civicforest.local` (Next.js) and `api.civicforest.local` (Django),
both browser-trusted via `mkcert`.

---

## Repository layout

```
CivicForest/
├── implementation_plan.md   ← this file
├── tasks.md                 ← progress checklist
├── README.md                ← run instructions only
├── docker-compose.yml
├── Makefile
├── .env.example
├── caddy/Caddyfile
├── .github/workflows/ci.yml
├── backend/
│   ├── pyproject.toml            # uv-managed
│   ├── manage.py
│   ├── config/
│   │   ├── settings/{base,local,production}.py
│   │   ├── urls.py · asgi.py · wsgi.py · celery.py
│   └── apps/
│       ├── common/     # UUIDTimestampedModel, pagination, exceptions
│       ├── accounts/   # custom User, allauth config, addresses
│       ├── catalog/    # Category, Product, ProductVariant, Image, Material, Tag
│       └── search/     # Meili index, suggestion endpoint, fallback
└── frontend/
    ├── package.json · tsconfig.json · next.config.ts · tailwind config
    ├── app/
    │   ├── (storefront)/  # home, collections, shop, product, search, about, contact
    │   └── (account)/     # login (more later: cart, checkout, profile)
    ├── components/{layout,product,search,ui}/
    └── lib/{api,auth,brand}/
```

---

## Phased delivery

Follows `plan.md` §18 build order. **This session covers phases 1–5** (the
foundation slice). Later phases are scoped but deferred.

### Phase 1 — Scaffold, Docker, local HTTPS, CI skeleton
- Monorepo dirs, `.gitignore`, `.env.example` (documented, committed).
- `docker-compose.yml`: `postgres`, `redis`, `meilisearch`, `backend`, `worker`,
  `beat`, `frontend`, `caddy`.
- `caddy/Caddyfile` terminating TLS and routing `/` vs `/api` `/_allauth` `/admin`.
- `Makefile`: `up`, `down`, `migrate`, `seed`, `test`, `lint`, `certs`.
- Lint config: `ruff` (Python), `eslint`/`prettier` (JS). GitHub Actions `ci.yml`
  running lint only for now.

### Phase 2 — accounts + allauth headless + Next.js login
- Custom `User` (UUID pk, email as `USERNAME_FIELD`), Argon2id primary hasher.
- `Address` model (shipping/billing).
- django-allauth in **headless** mode; DRF `SessionAuthentication` + CSRF enforced.
- Security settings: secure/httponly/samesite cookies, HSTS, nosniff, frame-deny,
  scoped throttles (stricter on auth).
- Next.js `/login` matching the mockup (split hero + form, Google/Apple buttons,
  remember-me, forgot-password), wired to `/_allauth/browser/v1`.

### Phase 3 — catalog + admin + seed
- `common.UUIDTimestampedModel` mixin, `StandardResultsPagination` (hard max size),
  consistent exception handler.
- Models: `Material`, `Category` (self-FK parent), `Tag`, `Product`, `ProductVariant`
  (size/color/sku/price_override/stock), `ProductImage`.
- `services.py` for catalog queries (active-only, prefetch, price resolution).
- Serializers: list vs detail, explicit fields.
- Read-only DRF viewsets: categories, products (filter by category/size/color/price/
  material), product detail by slug.
- Hardened admin: env-driven URL path, MFA-ready, editable catalog.
- `seed_catalog` management command: 5 categories (T-Shirts, Hoodies, Sweatshirts,
  Jackets, Bottoms — per the filter panel), Materials, and demo products/variants
  using the brand photos, so the storefront renders real data.

### Phase 4 — storefront pages
- Design tokens from the mockups: charcoal `#0E0E0D`/`#1A1713`, gold `#C89B4A`,
  cream `#F4F1EA`; serif display (Playfair-style) + clean sans body; cF monogram.
- Shared layout: top announcement bar, sticky nav with search/account/cart, footer
  with the four link columns + newsletter.
- **Home**: hero ("STYLE THAT SPEAKS"), 4-up feature strip, "Find Your Style"
  category grid, "Just Landed" new-arrivals row, brand-values band.
- **Collections**: hero + collection cards + values band.
- **Shop**: filter sidebar (category/size/color/price/material) + product grid +
  "Showing 1–12 of N" + pagination + sort.
- **Product detail**: gallery, variant pickers, price, add-to-cart (UI), details.
- All fetch live data via `lib/api` from `/api/v1/catalog`.

### Phase 5 — search
- `search` app: Meilisearch index definition, signal→Celery upsert, suggestion +
  full-search endpoints returning **minimal** payloads; **Postgres `icontains`
  fallback** when Meili is unreachable so the feature always works.
- Client: `useSearchSuggestions` hook — ≥2 chars, ~200ms debounce, `AbortController`
  cancellation, stale-response guard, last-20 in-memory cache, keyboard nav.
- Full **search results page** matching the mockup (query echo, result count,
  filter sidebar, grid, pagination, sort).

---

## Deferred (scoped, not built this session)

Tracked here so nothing is silently dropped:

- **cart / wishlist** persistence + coupon validation (server-side only).
- **orders** state machine + invoice; **payments** (Razorpay order + webhook, raw-body
  HMAC verify, idempotency).
- **custom_orders** upload → content-sniff/re-encode → print-partner (Printful/Printify)
  with idempotency keys.
- **Celery** depth (beyond wiring), reconciliation jobs.
- **CI/CD** hardening: CodeQL, Dependabot, secret scanning, Trivy, branch protection.
- **Observability**: Sentry, `/healthz` `/readyz`, structured logging, alerting.
- **Testing** breadth: full pytest suite, Playwright E2E, k6 load test, axe pass.
- Social-login provider credentials (Google/Apple) — UI is built, keys are env-gated.

---

## Verification for this slice

- Backend: `manage.py check`, `makemigrations --check`, `migrate`, targeted `pytest`.
- Frontend: `tsc --noEmit` / `next build`.
- Honest status of what runs standalone vs. what needs Docker services (Postgres,
  Meilisearch) is recorded in `tasks.md` and the final summary.

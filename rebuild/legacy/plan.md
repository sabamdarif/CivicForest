## 1. Core Technology Decisions

| Layer | Choice | Why |
|---|---|---|
| Backend framework | Django 5.2 LTS | 5.2 LTS is supported with security fixes until April 2028, unlike the standard 8‑month release track (e.g. 6.0), which is EOL far sooner. Stability matters more than latest features for a payments-handling app. |
| Database | PostgreSQL 17.x | 18.4 is the newest stable release, but 17.x is what most managed providers (RDS, Cloud SQL, DigitalOcean, Supabase) fully support today with mature tooling. Use whichever your host's newest supported version is at deploy time. |
| API layer | Django REST Framework, internal-only (session-cookie auth, not a public token API) | Matches your stated need — no external consumers, so you don't need OAuth2/public API-key infrastructure. |
| Auth | django-allauth in **headless mode** | Headless allauth exposes signup/login/social-login/MFA/password-reset as JSON endpoints while still using Django's session framework underneath, with a documented React reference integration. This avoids hand-rolling JWT storage/refresh logic in the browser, which is the single biggest source of home-grown auth bugs. |
| Frontend | **Next.js (App Router)**, not a plain Vite SPA | You asked "whichever is best and future-proof." For a public storefront, SEO is a real revenue channel (people search "printed t-shirts India"). Vite SPAs ship a near-empty HTML shell, hurting indexing and first paint; Next.js pre-renders product/category pages as HTML, which is the standard recommendation for e-commerce. Everything logged-in (cart, account, checkout, custom-order studio) is rendered as ordinary client components — so it's not "more React" work, just SSR for the pages that need it. |
| Search engine | Meilisearch | For a catalog this size, Meilisearch gives typo-tolerant, sub-50ms prefix search out of the box, versus days of tuning Postgres `pg_trgm`/`tsvector` for the same UX, and versus the heavier ops burden of Elasticsearch/OpenSearch. |
| Task queue | Celery + Redis | Payment webhooks, print-provider API calls, and email all need retries, backoff, and chaining. Celery is heavier to operate than RQ/Dramatiq, but for money-touching workflows the retry/chain/idempotency tooling is worth the extra complexity. |
| Payments | Razorpay | For an India-based store in 2026, Razorpay remains the standard default for developer experience, UPI support, and webhook reliability; revisit only once you clear meaningful monthly volume. |
| Print fulfillment | Printful or Printify REST API (OAuth/Personal Access Token) | Both expose product/variant catalogs, order creation, and status webhooks — matches your "send custom order to a print partner" requirement exactly. |
| File/media storage | S3-compatible object storage (Cloudflare R2 or AWS S3) | Never store user-uploaded design files or product images on the app server's local disk — no durability, no horizontal scaling. |
| Local HTTPS | mkcert + Caddy reverse proxy in Docker Compose | This is the standard pattern for matching your "https everywhere, even locally" requirement without fighting self-signed-cert browser warnings. |
| CI security | GitHub CodeQL (default setup) + Dependabot + secret scanning + Trivy for images | CodeQL's default setup auto-detects languages and needs no workflow file to maintain; add the advanced/custom workflow only if you later need custom query packs. |

---

## 2. High-Level Architecture

- **Three deployable units**: `web` (Django/DRF + Gunicorn, ASGI via Uvicorn workers for async webhook handling), `worker` (Celery), `frontend` (Next.js standalone server).
- **Supporting services**: PostgreSQL (managed, not self-hosted, so you get automated backups/PITR for free), Redis (Celery broker + cache + rate-limit store), Meilisearch, object storage.
- **Single top-level domain**, split by subdomain or path at the reverse proxy: e.g. `civicforest.com` → Next.js, `api.civicforest.com` → Django. Keeping both under `civicforest.com` (not two unrelated domains) lets allauth's session cookie be scoped to the parent domain so both the SSR layer and the browser can send it — this is what makes cookie-based auth work cleanly with a separate frontend server.
- **Reverse proxy** (Caddy in both environments) terminates TLS, forwards `/` to Next.js and `/api/`, `/media/`, `/_allauth/` to Django. Using the same proxy software in dev and prod is what gives you real dev/prod parity, not just "https exists in both."
- **Data flow for a request**: browser → Caddy (TLS termination) → Next.js (renders SSR pages, or passes through to client-side fetch) → Django REST API → Postgres/Redis/Meilisearch. Celery workers pick up async jobs pushed by Django views (payment confirmation, print-order submission, emails, search re-indexing).

---

## 3. Codebase Structure

**Two repositories or a monorepo with two top-level folders** (`backend/`, `frontend/`) — either works; a monorepo is simpler for a solo/small team since PRs touching both sides stay atomic.

Backend Django apps, split by bounded responsibility (not one giant `core` app):
- `accounts` — allauth config, custom user model, addresses, MFA settings.
- `catalog` — Category, Product, ProductVariant (size/color/material/price/stock), ProductImage, Tag.
- `search` — Meilisearch index definitions, sync signals/tasks, suggestion endpoint, search-analytics logging.
- `cart` — server-side cart/session logic, coupon validation.
- `orders` — Order, OrderItem, order state machine, invoice generation.
- `custom_orders` — design upload handling, print-provider integration, print-job status tracking.
- `payments` — Razorpay order creation, webhook verification, payment reconciliation.
- `wishlist` — saved items per user.
- `reviews` (if/when you want it) — kept separate so it can be deferred without touching `catalog`.
- `common`/`core` — shared base models (UUID + timestamps mixin), pagination classes, exception handling, permission base classes.

Conventions:
- Each app: `models.py`, `serializers.py`, `views.py` (or `viewsets.py`), `permissions.py`, `services.py` (business logic kept out of views/serializers so it's testable and reusable from Celery tasks), `tasks.py`, `tests/`.
- **Fat services, thin views/serializers.** Views only orchestrate: validate input → call a service function → return a response. This is what lets the same logic run from an admin action, a Celery task, and an API view without duplication.
- Settings split into `base.py`, `local.py`, `staging.py`, `production.py`, all reading secrets from environment variables — never hardcoded, never `local.py`-only defaults leaking into prod.
- Comment policy: comments only where the *why* isn't obvious from the code itself (a non-obvious business rule, a workaround for a library quirk, a security-relevant decision). No comments restating what a line does.

Frontend structure (Next.js App Router):
- `app/(storefront)/` — home, shop/category, product detail, search results, contact — SSR/ISR.
- `app/(account)/` — cart, checkout, orders, wishlist, profile — client-rendered, auth-gated.
- `lib/api/` — a single typed API client wrapping fetch calls to Django, so no component calls `fetch` directly.
- `lib/auth/` — thin wrapper around allauth's headless endpoints (session check, login, logout, social login redirect).
- `components/` split by domain (`product/`, `cart/`, `search/`, `checkout/`), not one flat folder.

---

## 4. Data Model (matches your screenshots)

- **Category**: name, slug, parent (nullable, for future subcategories), is_active. Seed exactly 5 defaults (T‑Shirts, Hoodies, Sweatshirts, Jackets, Bottoms — matching your filter panel) via a data migration or a one-time management command, not hardcoded in code — so they show up in the admin as normal editable rows from day one.
- **Product**: name, slug, description, category (FK), material (choice or FK to a Material table so it's admin-configurable), base_price, is_new, is_bestseller, is_active, meta fields for SEO (title/description) since Next.js will render these server-side.
- **ProductVariant**: product (FK), size, color, sku, price_override (nullable — falls back to product base price), stock_quantity, is_active. This is what your filters (size/color/price) and "Showing 1–12 of 48" pagination map onto.
- **ProductImage**: variant or product level, ordering, alt text.
- **Wishlist**: user, product/variant, created_at.
- **Cart / CartItem**: tie to session for guests and to user after login (merge on login), variant, quantity.
- **Coupon**: code, discount type (percent/flat), min order value, max uses, expiry, active flag — validated **only** server-side at checkout, never trusted from the client.
- **Order / OrderItem**: order number (public, non-guessable — see Security), status enum (`created → payment_pending → paid → processing → shipped → delivered → cancelled → refunded`), shipping address, computed totals (recomputed server-side, never accepted from client), coupon applied, payment reference.
- **CustomDesignOrder**: linked to an Order, uploaded design file reference (object storage key, not a public URL), placement/product/variant chosen, print-provider order id, print-provider status, internal review status.
- **Payment**: gateway, gateway_order_id, gateway_payment_id, signature, verified_at, raw webhook payload (for audit, PII-scrubbed).

Use **UUID primary keys** (or a separate public "order number" field) for anything referenced in URLs a customer can see (orders, custom design orders) — sequential integer IDs let anyone enumerate `/orders/1`, `/orders/2`... to probe for other people's data.

---

## 5. Authentication & Authorization

- django-allauth in headless mode, with the **session token strategy** (cookie-based), not JWT — since frontend and backend share a top-level domain, cookies are simpler and safer than storing tokens in JS-accessible storage.
- Social login: Google and Apple (as shown in your login screen), configured as allauth social providers; allauth's headless flows already return the right redirect/callback shape for a SPA/Next.js frontend.
- Cookie flags: `Secure` always on (safe since you're HTTPS everywhere including local dev), `HttpOnly` on the session cookie, `SameSite=Lax` (Strict would break some OAuth redirect flows).
- CSRF: DRF's session authentication enforces Django's CSRF middleware — keep it on for all mutating requests; the CSRF cookie itself is not `HttpOnly` by design (JS must read and echo it), but it's still `Secure` + `SameSite`.
- MFA: enable allauth's built-in TOTP MFA and **require it for any staff/superuser account**, even if optional for regular customers.
- Password hashing: Argon2id as the primary hasher (add `argon2-cffi` and put Argon2PasswordHasher first in `PASSWORD_HASHERS`) — stronger against GPU cracking than PBKDF2 default.
- Authorization: every view scopes querysets to `request.user` (or session for guest cart) — never trust an ID passed by the client without an ownership check. Role checks (staff-only actions) always re-verified server-side, never inferred from anything the client sends.

---

## 6. REST API Design

- Versioned from day one (`/api/v1/...`) even as a private API — it costs nothing now and saves a painful migration later when you eventually add a mobile app.
- DRF ViewSets/generic views per resource, with **explicit serializer fields** — never `fields = "__all__"` on any writable serializer, and separate read vs. write serializers wherever a model has fields that must never be client-writable (price, stock, order status, is_staff, etc.).
- Pagination: cursor or limit/offset with a **hard server-side max page size** — don't let a client request `?page_size=10000` and scrape your catalog in one call.
- Throttling: DRF scoped throttle classes per endpoint class — stricter on auth endpoints (login/signup/password-reset), generous but capped on catalog browsing, separately tuned for the search-suggestion endpoint (see below).
- Standard error shape across the API (consistent error code + message structure) so the frontend can handle failures generically instead of per-endpoint parsing.
- CORS: `django-cors-headers` with an **explicit allow-list** of your own frontend origin(s) — never a wildcard, since credentials (cookies) are involved.
- API docs generated from DRF (drf-spectacular/OpenAPI schema) purely for your own internal reference — not exposed publicly in production.

---

## 7. Search System Design (deep dive)

You specifically asked for YouTube-style behavior without "studio" per-keystroke requests. Here's the full design, client and server:

**Client-side (Next.js/React):**
- Debounce keystrokes (roughly 150–250ms trailing debounce) before firing a suggestion request — this alone eliminates most redundant calls.
- Enforce a **minimum query length** (e.g. 2 characters) before any network call fires at all.
- Use an `AbortController` to cancel the previous in-flight suggestion request the instant a new keystroke fires — otherwise a slow earlier response can arrive after a faster later one and overwrite the correct suggestions on screen (a classic race condition).
- Before rendering a response, compare its originating query string against the *current* input value; discard it silently if the user has since changed the box.
- Keep a small **in-memory client cache** (e.g. last 20 queries → results) keyed by the exact query string, so retyping something you already searched (or backspacing back to it) is instant with zero network round-trip.
- The suggestion endpoint returns a **minimal payload** — just what's needed to render a dropdown (name, slug, thumbnail, price, category) — never the full product detail payload. A separate, heavier endpoint powers the full results page (your "Showing 1–12 of 48" screen) when the user actually submits the search, with pagination, sorting, and the full filter panel (category/size/color/price/material) shown in your screenshot.
- Keyboard navigation (arrow keys + Enter) in the dropdown, matching the pattern users expect from YouTube/Google.

**Server-side:**
- The suggestion endpoint queries **Meilisearch directly, not Postgres** — autocomplete-speed queries against the primary transactional database compete with checkout/order traffic and don't scale the way a purpose-built search index does.
- **Never keep the search index synchronously coupled to the write path.** When a product/variant is created, updated, or its stock changes, a Django signal enqueues a Celery task that upserts the corresponding Meilisearch document. A nightly reconciliation job does a full re-sync as a safety net against any missed signal/failed task.
- **Denormalize into the index** exactly the fields the suggestion/search UI needs (name, slug, thumbnail URL, price, category name, available sizes/colors) so a query never needs to join back to Postgres mid-request.
- Configure Meilisearch's searchable-attribute ordering (name should outrank description/category in relevance) and enable its built-in typo tolerance and prefix search — this is what gives you the "type 3 letters, get sensible results" feel without you writing fuzzy-matching logic yourself.
- Rate-limit the suggestion endpoint per IP/session (DRF throttle + a reverse-proxy-level limit as defense in depth) — autocomplete endpoints are a common target for scraping/DoS because they look "free" to hammer.
- Cache **popular/anonymous** query results briefly (short TTL in Redis or at the CDN/reverse-proxy edge) — most autocomplete traffic clusters around a small set of common prefixes.
- Log search queries (query text + result count + whether it converted to a click) to a lightweight analytics table — this is what eventually lets you tune ranking and see what people search for that you don't stock.
- **Graceful degradation**: if Meilisearch is unreachable, fall back to a simple Postgres `icontains`/trigram query for the full-results page rather than showing an error — degraded search beats broken search.

---

## 8. Custom Design Orders → Print Partner Integration

- On the product page's "custom design" option, the customer uploads an image client-side. The client does *cosmetic* validation only (file type/size hint, preview) — this is purely UX, never trusted.
- The file is uploaded to your Django backend (never directly to the print partner from the browser, since that would require exposing print-partner credentials client-side). The backend:
  - Re-validates MIME type by content sniffing (not just file extension), enforces a max size/dimension limit, and re-encodes the image (e.g. re-saving through an imaging library) to strip EXIF metadata and neutralize embedded payloads.
  - Stores the file in object storage under a randomized key, not publicly accessible — served only via short-lived signed URLs.
  - Creates a `CustomDesignOrder` in a `pending_payment` state.
- Only **after payment is confirmed** (see below) does a Celery task call the print partner's API (Printful/Printify) to create the actual print job, using a signed URL to the design file. This call uses an **idempotency key** (e.g. your internal order ID) so a retried task never creates a duplicate print job.
- The print partner's webhook (shipped/fulfilled/failed) updates your `CustomDesignOrder` status and, in turn, the parent `Order` status, and triggers a customer notification email.
- Keep a manual "flagged for review" state for anything that fails automated content checks (e.g. suspicious file type), so you can eyeball it before it reaches the print partner — this also gives you a natural place to add copyright/appropriateness review later without re-architecting anything.

---

## 9. Payments (Razorpay)

- Checkout flow: client requests order creation → **Django computes the final amount from the database** (product prices + variant + coupon validity + shipping rule), never from anything the client submits → Django calls Razorpay's Orders API server-to-server → returns the Razorpay order ID to the client → client renders Razorpay's hosted checkout.
- On completion, the client receives a payment ID/order ID/signature and posts it to your backend, which verifies the HMAC-SHA256 signature — but this client-side callback is **not** treated as the authoritative confirmation.
- The **source of truth for "this order is actually paid" is Razorpay's server-to-server webhook**, verified against the raw (unparsed) request body using your separate webhook secret. Verifying against the raw body — not a re-serialized JSON object — is essential, since re-encoding can silently change byte-for-byte content and break the signature check.
- Webhook handling is idempotent: store the event ID and skip processing if already seen, since providers retry deliveries.
- Because you never touch raw card data (Razorpay's checkout handles it entirely), your PCI-DSS scope stays minimal (SAQ‑A tier) — don't build any custom card-entry form yourself.
- Order fulfillment (stock decrement, print-job trigger, confirmation email) is only kicked off from the verified webhook handler, run inside a database transaction with row-level locking on the affected stock rows, so two near-simultaneous payments can't both succeed against the last unit of stock.

---

## 10. Client-Side vs. Server-Side Responsibility (explicit boundary)

Since you specifically asked for this to be thought through:

**Always server-side, never trust the client for:**
- Final price/total calculation, coupon validity and discount amount, stock availability checks, order status transitions, payment verification, print-partner API calls and credentials, role/permission checks, search index writes, rate limiting, file content validation for uploads.

**Fine — even better — client-side:**
- Form field validation for UX responsiveness (still re-validated server-side), search debounce/caching/keyboard navigation, cart quantity stepper UI state before submit, wishlist heart toggle optimistic UI (reconciled with server response), image preview before upload, client-side routing/prefetching, non-sensitive display formatting (currency formatting, relative dates).

The rule of thumb: if getting it wrong costs you money, data integrity, or someone else's privacy — it's server-side, full stop, even if that duplicates a check the UI already does.

---

## 11. Admin Panel & Staff Access

- Django admin stays enabled in production (you need it to manage categories/products/orders) but is **hidden and hardened**, not literally disabled:
  - The admin URL path is a random, non-guessable string read from an environment variable — never the default `/admin/`.
  - At the reverse proxy/firewall layer, restrict that path to an IP allow-list (your and any co-developer's static IP/VPN range) or put it behind a Zero-Trust access layer (e.g. Cloudflare Access with email-based one-time codes) so unauthenticated requests never even reach Django for that path — a request from an unlisted IP should get a generic 404, not a login page, so the admin's existence isn't even confirmed to scanners.
  - MFA required for every staff/superuser account (allauth's TOTP support).
  - Shorter session timeout specifically for staff sessions.
  - All admin changes logged (Django's built-in `LogEntry`, optionally extended with `django-auditlog` for full before/after field diffs) so you have an audit trail if an account is ever compromised.
  - `DEBUG=False` and Django's debug toolbar/docs completely excluded from production dependencies, not just settings-flagged off.

---

## 12. Security — Scenario Checklist

Beyond what's covered above:

- **SQL injection**: ORM-only, parameterized queries; if raw SQL is ever unavoidable, parameterize it explicitly, never string-format.
- **XSS**: React escapes by default — avoid `dangerouslySetInnerHTML`; any rich text (product descriptions) is sanitized server-side against an allow-list before storage, plus a Content-Security-Policy header restricting script sources.
- **Clickjacking**: `X-Frame-Options: DENY` / CSP `frame-ancestors 'none'`.
- **Session hijacking**: session ID rotated on login, `Secure`+`HttpOnly`+`SameSite` cookies, step-up re-authentication before sensitive actions (changing email/password, viewing saved payment info).
- **Brute force**: throttling + backoff on login/password-reset, generic error messages that don't reveal whether an email is registered.
- **Mass assignment / IDOR**: explicit serializer fields, UUIDs for externally-referenced records, ownership checks on every object-level view.
- **File upload abuse**: covered in section 8 — content-sniffed MIME validation, size/dimension caps, re-encoding, private storage with signed URLs, no execution paths.
- **SSRF**: if the backend ever fetches a URL on the server's behalf (e.g. an image by URL), validate the destination against an allow-list and don't blindly follow redirects.
- **Webhook spoofing/replay**: raw-body signature verification with per-provider secrets, timestamp freshness checks, idempotency-key/event-ID dedup tables.
- **Secrets management**: environment variables in all environments, a proper secrets manager in production (Doppler/Vault/your cloud provider's secret store), pre-commit secret-scanning locally in addition to GitHub's server-side scanning, periodic key rotation.
- **Dependency risk**: Dependabot + CodeQL + `pip-audit`/`npm audit` in CI, lockfiles pinned (`uv.lock`/`pip-tools`, `package-lock.json`), container base images scanned (Trivy) and pinned by digest.
- **Open redirect**: any post-login/checkout redirect parameter validated against an internal allow-list of paths.
- **Rate limiting/DoS**: per-endpoint DRF throttles plus reverse-proxy/CDN-level limits, request body size caps, hard pagination ceilings.
- **Data privacy**: since you're collecting Indian customers' names/addresses/phone numbers, follow India's DPDP Act basics — explicit opt-in for marketing emails, a real privacy policy, a data-deletion request process, encryption at rest via your managed Postgres provider.
- **Backups**: automated encrypted backups with point-in-time recovery on the managed database, and an actual periodic *restore test* (an untested backup is not a backup).

---

## 13. Docker & Local HTTPS Development

- `docker-compose.yml` services: `postgres`, `redis`, `meilisearch`, `django` (with hot-reload), `celery-worker`, `celery-beat`, `next` (dev server), `caddy` (reverse proxy + TLS termination).
- Generate a local Certificate Authority once with `mkcert -install`, then issue a certificate for your chosen local hostnames (e.g. `civicforest.local`, `api.civicforest.local`) mounted into the Caddy container — this gives every developer a browser-trusted HTTPS cert with no warnings, matching production TLS behavior exactly rather than approximating it.
- Because HTTPS is on in both environments, cookie `Secure` flags, HSTS, and CSP can be configured identically everywhere — no `if DEBUG` branching around cookie security, which is itself a common source of "works locally, breaks in prod" security bugs.
- `.env.local`, `.env.staging`, `.env.production` (never committed) for environment-specific secrets, loaded via Docker Compose env files.
- A `Makefile` or a small set of shell scripts wrapping common commands (`up`, `migrate`, `seed`, `test`, `lint`) so onboarding a second developer is a couple of commands, not a wiki page.

---

## 14. CI/CD & Automated Security Scanning

- GitHub Actions pipeline stages: lint (ruff/black for Python, eslint/prettier for JS) → type check (mypy, TypeScript) → unit tests → integration tests (spun up against an ephemeral Postgres/Redis service in the CI runner) → build container images → scan images (Trivy) → push to registry → deploy.
- **CodeQL**: enable default setup first (zero-config, auto-detects Python/JavaScript) — only move to a custom advanced workflow later if you need custom query packs.
- **Dependabot**: weekly PRs for both `pip`/`uv` and `npm` ecosystems, plus Dependabot security alerts.
- **Secret scanning + push protection** enabled at the repo level so accidental credential commits are blocked before they land.
- Branch protection on `main`: required passing CI (including CodeQL), required review, no direct pushes.
- Deploys run database migrations as an explicit release step before traffic is switched, with all migrations written to be backward-compatible with the previous release (so a rollback never leaves the schema in an unrunnable state).

---

## 15. Testing Strategy

- Backend: `pytest-django` + `factory_boy`/Faker for fixtures; DRF `APIClient` tests per endpoint (happy path + permission-denied + validation-failure cases); dedicated tests for the payment-webhook signature verification and the search-index sync signals, since these are the highest-blast-radius code paths.
- External integrations (Razorpay, print partner): tested against recorded/mocked responses, never live calls in CI.
- Frontend: component tests (Vitest + React Testing Library) plus end-to-end tests (Playwright) for the critical paths — signup/login, search → add to cart → checkout happy path, custom design upload flow.
- A basic accessibility pass (axe) on key pages, given how much UI you're shipping.
- A short load test (k6) against the search suggestion endpoint before launch, since that's the one endpoint designed to be hit constantly.

---

## 16. Observability

- Structured JSON logging with a request/correlation ID threaded through Django, Celery tasks, and the reverse proxy logs, so a single failed checkout can be traced end-to-end.
- Error tracking (e.g. Sentry) wired into both Django and Next.js.
- Health-check endpoints (`/healthz`, `/readyz`) excluded from rate limiting and auth, used by your orchestrator/load balancer.
- Alerting specifically on: failed webhook signature verifications, Celery task failure rate, and any payment/order-status mismatch (money in a limbo state is the failure mode you most want to know about immediately).

---

## 17. Documentation Practice

- A root `README.md`: setup instructions only (how to run locally), not a running log.
- A separate `PROGRESS.md` (or `docs/log/YYYY-MM.md` if it grows): short, bullet-point entries per milestone — what was built, what decision was made and why, what's left — written after each meaningful chunk of work, kept intentionally brief so it stays something you'd actually reread rather than skim past.
- Lightweight ADRs (architecture decision records) only for decisions that were genuinely debated (e.g. "why Meilisearch over pg_trgm") — one file per decision, a few bullet points, not essays.

---

## 18. Suggested Build Order

1. Repo scaffold, Docker Compose + local HTTPS, CI skeleton with linting only.
2. `accounts` app + allauth headless + Next.js auth wiring — get login/signup working end-to-end first, since everything else depends on it.
3. `catalog` app + admin-managed categories/products/variants + seed data for the 5 default categories.
4. Storefront pages (home, shop, product detail) in Next.js, server-rendered against the catalog API.
5. `search` app + Meilisearch + suggestion endpoint + full search results page.
6. `cart`/`wishlist` + coupon logic.
7. `orders` + Razorpay checkout + webhook handling.
8. `custom_orders` + print-partner integration.
9. Admin hardening (hidden path, MFA, IP allow-list) — do this *before* go-live, not after.
10. CodeQL/Dependabot/secret scanning turned on, branch protection enforced.
11. Observability (Sentry, health checks, alerting) wired in before real traffic.
12. Load test the search endpoint, run a full security pass against the checklist in section 12, then launch.

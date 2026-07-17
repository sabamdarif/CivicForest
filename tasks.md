# CivicForest — Task Checklist

Progress tracker. Companion to [`implementation_plan.md`](./implementation_plan.md)
(phases 1–5) and [`remaining_plan.md`](./remaining_plan.md) (phases 6–12). Checked as
work lands.

Legend: `[ ]` todo · `[~]` in progress · `[x]` done · `[-]` deferred

---

## 📊 Progress summary

**Foundation slice (1–5): ✅ done.  Commerce backend (6–8): ✅ done & verified.
Frontend for 6–8: ✅ done.  Hardening (9–11): ✅ mostly done.**
The whole purchase path now exists end-to-end: cart → coupon → checkout → Razorpay
→ verified webhook → stock decrement → custom-print submission to **Qikink** →
status/tracking polling — with the storefront UI for all of it, plus admin hardening
(Caddy IP allow-list + staff TOTP + auditlog), CI with tests/audits/Trivy, and
observability (Sentry, JSON logs, correlation IDs, order emails).

| Area | Status |
|------|--------|
| Phase 0 — Planning docs | ✅ Done |
| Phase 1 — Scaffold, Docker, local HTTPS, CI | ✅ Done |
| Phase 2 — accounts + allauth headless + login | ✅ Done |
| Phase 3 — catalog + admin + seed | ✅ Done |
| Phase 4 — storefront pages | ✅ Done |
| Phase 5 — search (suggest + results + fallback) | ✅ Done |
| **Phase 6 — cart / wishlist / coupons (backend)** | ✅ **Done** |
| **Phase 7 — orders + Razorpay payments (backend)** | ✅ **Done** |
| **Phase 8 — custom orders + Qikink print (backend)** | ✅ **Done** |
| Phase 9 — admin hardening | ✅ Done |
| Phase 10 — CI/CD security scanning | 🟡 Mostly done (repo-settings items remain) |
| Phase 11 — observability | 🟡 Mostly done (alert rules remain) |
| Phase 12 — testing breadth & launch | 🟡 Partial (unit tests done; no E2E/k6/axe) |
| **Frontend for phases 6–8 (cart/checkout/orders UI)** | ✅ **Done** (build + lint green) |

**Verification (this machine, `USE_SQLITE=1`):**
- `manage.py check` → 0 issues · `makemigrations --check` → **no drift**
- `pytest` → **52 passed** (was 7 → **+45 new tests** this session)
- `ruff check` + `ruff format --check` → clean across all apps + config

**Test breakdown:** accounts 3 · catalog 4 · **cart 11** · **orders 11** ·
**payments 9** · **custom_orders 14**.

**Roughly where the whole product stands:** foundation + commerce backend + frontend +
hardening ⇒ **~85–90% of the end-to-end store**. What's left is **test breadth**
(E2E/load/a11y, factory_boy), GitHub repo settings (CodeQL/secret scanning/branch
protection), alert rules in Sentry, and live credentials. None of the code needs
external keys to *run* offline; going live needs Razorpay + Qikink credentials, Redis,
SMTP, and object storage (below).

---

## Phase 6 — cart / wishlist / coupons  ✅ (backend)
- [x] `cart` app: `Cart`, `CartItem`, `Coupon`, `Wishlist` models (+ migration)
- [x] `services.py`: `get_or_create_cart`, `add_item`/`set_item_quantity`/`remove_item`
      (stock re-checked every mutation), `apply_coupon`/`remove_coupon`,
      `price_cart` (single source of truth), `merge_guest_cart_into_user`
- [x] Server-side shipping rule (flat ₹59, free ≥ ₹999) — set in `settings`
- [x] Read/write serializers (money fields read-only), thin `APIView`s
- [x] URLs: `/api/v1/cart`, `/cart/items[/<variant_id>]`, `/cart/coupon`,
      `/wishlist[/<product_id>]`
- [x] Guest→user cart merge on login (allauth `user_logged_in` signal)
- [x] Admin (Coupon/Cart/Wishlist)
- [x] Tests (11): stock caps, coupon percent/expiry/min-order/max-uses, merge sums+caps,
      shipping rule, guest-cart isolation (IDOR)
- [ ] **Frontend** cart drawer/page, coupon UI, wishlist persistence → task #5

## Phase 7 — orders + Razorpay payments  ✅ (backend)
- [x] `orders` app: `Order` (non-guessable `order_number`, snapshotted totals+address,
      status **state machine**), `OrderItem` (purchase-time snapshot) (+ migration)
- [x] `services.py`: `create_order_from_cart` (server re-price), guarded `transition`,
      `reserve_stock` (`select_for_update` row locks), `fulfil_paid_order` (idempotent)
- [x] `payments` app: `Payment`, `WebhookEvent` (event dedup) (+ migration)
- [x] `gateway.py`: Razorpay order create (stdlib, no new dep) + **HMAC-SHA256**
      signature verify (payment callback **and** raw-body webhook)
- [x] `POST /api/v1/checkout` (create order + Razorpay order, amount computed server-side)
- [x] `POST /api/v1/payments/verify` (advisory callback) ·
      `POST /api/v1/payments/webhook/razorpay` (**authoritative**, no CSRF, raw-body verify)
- [x] `GET /api/v1/orders[/<order_number>]` — ownership-scoped (no IDOR)
- [x] Admin (immutable Order/OrderItem, Payment, WebhookEvent)
- [x] Tests (11+9=20): totals snapshot, order-number format, empty-cart block,
      legal/illegal transitions, **last-unit reservation guard**, checkout API,
      order IDOR (list + 404 detail), signature valid/invalid, webhook fulfil +
      stock decrement + cart clear, **replay idempotency**, bad-signature reject,
      coupon-usage increment, `to_paise`
- [ ] **Frontend** checkout page + Razorpay hosted checkout + `/account/orders` → task #5

## Phase 8 — custom design orders → Qikink  ✅ (backend)
- [x] `custom_orders` app: `CustomDesignOrder` (order/variant FK, private design file,
      `review_status`, `submit_status`, unique `idempotency_key`, Qikink id/status/AWB)
- [x] `uploads.py`: size cap → **content-sniff MIME** (`filetype`) → Pillow verify +
      dimension cap → **re-encode to clean PNG (strips EXIF/payloads)**
- [x] `qikink.py`: `QikinkClient` — token exchange (**cached in Redis**), `create_order`,
      `get_order_status`; base URL + paths settings-driven; **host allow-list (SSRF)**;
      single mockable `_send`
- [x] `services.py`: `build_order_payload` (buyer's address, `qikink_shipping=1`,
      `gateway=Prepaid`), idempotent `submit_to_qikink`, `apply_status` +
      **Qikink→Order status map**
- [x] `tasks.py`: `submit_custom_order_to_qikink` (enqueued from verified webhook only),
      `poll_custom_order_statuses` (**Celery Beat**, since Qikink has no webhook)
- [x] Beat schedule wired in `config/celery.py` (poll every 20 min + nightly reindex)
- [x] `POST /api/v1/custom-designs` upload endpoint + read (ownership-scoped)
- [x] Admin with approve/reject review actions (manual gate before print)
- [x] Tests (14): valid re-encode, **renamed-exe rejected by sniff**, **EXIF stripped**,
      oversize + over-dimension + empty rejected, **submit idempotency**, flagged never
      submits, submit→processing, **token cached/reused**, status-map (Printed/In-Transit/
      Delivered), delivered→terminal
- [ ] **Frontend** design upload on product page + tracking in `/account/orders` → task #5

## Settings / URLs / env wiring  ✅ done
- [x] All new apps in `INSTALLED_APPS`; URLs mounted under `/api/v1`
- [x] `/readyz` readiness probe (DB + cache) added
- [x] Commerce settings block (shipping, Razorpay, **Qikink**, object storage) in `base.py`
- [x] Celery Beat schedule
- [x] Update `.env.example` with new keys (Razorpay, Qikink, S3/R2, shipping)
- [x] Update `README.md` §5+§6 — swap Printful/Printify → **Qikink**
- [x] Object storage backend: added `django-storages[s3]` + boto3; `STORAGES["default"]`
      switches to **private S3/R2 (signed URLs)** when `S3_BUCKET_NAME` is set — local disk
      otherwise (and always in `USE_SQLITE` offline/test mode)

---

## Deferred — remaining ~30%

### Phase 5 (task #5) — FRONTEND for cart / checkout / orders  ✅ DONE
- [x] `lib/api/{cart,wishlist,orders,customDesigns,account}.ts` typed clients + `types.ts` additions
- [x] `client.ts`: browser CSRF-token priming/echo on unsafe methods + FormData support
- [x] `CartProvider` (root-mounted, server-priced) + live nav badge; `WishlistProvider` + real heart persistence (`WishlistButton` replaces UI-only toggle on card + product page)
- [x] Cart drawer: qty stepper (server re-price each mutation), coupon input, **server totals**
- [x] Cart page (`/cart`) — full-page view
- [x] Wishlist page (`/account/wishlist`)
- [x] Checkout page: address prefill, Razorpay hosted checkout, poll order status
- [x] `/account/orders` list + detail (incl. custom-order tracking/AWB)
- [x] Custom-design upload UI on the product page (cosmetic validation + preview) — `CustomDesignUpload` wired into purchase panel
- [x] Signup + password-reset UI (allauth endpoints already exist; login is built)
- [x] `tsc --noEmit` + `next build` green — all 17 routes compile, `eslint .` clean

### Phase 9 — admin hardening (`remaining_plan.md` §9)  ✅ done
- [x] IP allow-list in front of the admin path (Caddy `@admin_blocked` matcher, env-driven
      `DJANGO_ADMIN_PATH` + `ADMIN_IP_ALLOWLIST`) → 404 for outsiders
- [x] Require TOTP MFA for all staff (`StaffAdminMiddleware`); shorter staff session
      timeout (`STAFF_SESSION_AGE`, default 1h)
- [x] `django-auditlog` before/after field diffs (Order, Coupon, Product, ProductVariant)

### Phase 10 — CI/CD & security scanning (`remaining_plan.md` §10)  🟡 mostly done
- [x] Extend `ci.yml`: typecheck → tests (ephemeral PG/Redis) → build → Trivy (SARIF → code scanning)
- [x] `pip-audit` (backend job) / `npm audit --audit-level=high` (frontend job)
- [-] CodeQL default setup, secret scanning + push protection, branch protection on
      `main` (Dependabot done earlier; rest are GitHub repo settings, not code)

### Phase 11 — observability (`remaining_plan.md` §11)  🟡 mostly done
- [x] `/readyz` (DB + cache) — done
- [x] Sentry (Django + Celery via `SENTRY_DSN`; Next.js via `@sentry/nextjs` +
      instrumentation hooks) — no-op when DSN unset, `send_default_pii=False`
- [x] Structured JSON logs (production formatter) + correlation IDs (`RequestIDMiddleware`
      → contextvar → log filter → Celery headers, echoed as `X-Request-ID`)
- [-] Alerts: webhook-verify failures, Celery failure rate, payment/order mismatch
      (configured in Sentry/monitoring dashboards, not code)

### Phase 12 — testing breadth & launch (`remaining_plan.md` §12)
- [x] Unit tests for the highest-blast-radius paths (webhook, state machine, uploads, Qikink)
- [-] `factory_boy` fixtures; broaden coverage
- [-] Playwright E2E (signup→login, search→cart→checkout, custom upload)
- [-] k6 load test on the suggestion endpoint; axe a11y pass
- [-] Full `plan.md` §12 security-checklist pass; DB backup restore test

### Cross-cutting
- [x] Object storage (R2/S3) switch wired for design uploads + media (private, signed
      URLs when `S3_BUCKET_NAME` set; local disk in dev/offline)
- [x] Email delivery (order confirmation / shipped / delivered) via SMTP env + Celery
      task (`apps.common.email`); console backend when `EMAIL_HOST` unset
- [-] Social-login provider credentials (Google/Apple) — UI built, keys env-gated
- [-] Live Razorpay + Qikink credentials (test-mode keys for dev; live access via dashboards)

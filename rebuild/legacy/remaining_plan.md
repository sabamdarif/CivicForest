# CivicForest — Remaining Implementation Plan (Phases 6–12)

The foundation slice (phases 1–5: infra, auth, catalog, storefront, search) is
**done and verified**. This document scopes the remaining **~60%** — commerce depth,
production hardening, and launch — as an execution-ready, dependency-ordered plan.

Companion to [`implementation_plan.md`](./implementation_plan.md) (phases 1–5) and the
architecture in [`plan.md`](./plan.md). Progress is tracked in [`tasks.md`](./tasks.md).

Guiding principles carry over unchanged: **fat services / thin views**, **never trust
the client** for money/stock/state/permissions, **explicit serializer fields**, **UUIDs
in customer-facing URLs**, **HTTPS everywhere**, comments only where the *why* isn't
obvious.

---

## Dependency order (why this sequence)

```
6 cart/wishlist ──► 7 orders/payments ──► 8 custom-print
                          │                     │
                          └──────► 11 observability (money paths need tracing first)
9 admin-hardening ─┐
10 CI/CD security ─┼─► can proceed in parallel with 6–8 (no functional coupling)
12 testing/launch ─┘   but must GATE go-live
```

- **6 → 7 → 8** is a hard chain: you can't check out without a cart, can't fulfil a
  print job without a paid order, can't create a print order before payment is verified.
- **9 (admin) / 10 (CI security)** have no functional dependency on the commerce chain
  and can land alongside it, but **must** be complete before go-live.
- **11 (observability)** is most valuable once real money paths exist (§7/§8), so it
  slots in right after payments.
- **12 (testing + security pass)** is the launch gate — nothing ships until it's green.

---

## Phase 6 — Cart & Wishlist (`plan.md` §4, §6, §10)

**Goal:** server-side, tamper-proof cart that survives login; persistent wishlist;
coupon model validated **only** server-side.

### Backend — new `cart` app
- Models
  - `Cart` — nullable `user` FK + `session_key` (guest carts keyed by session), one
    open cart per owner. `Coupon` applied here, not trusted from client.
  - `CartItem` — `cart` FK, `variant` FK, `quantity` (validated ≥1 and ≤ stock).
  - `Coupon` — `code` (unique), `discount_type` (`percent`|`flat`), `value`,
    `min_order_value`, `max_uses`, `used_count`, `expires_at`, `is_active`.
- `services.py` (the whole point — reused by orders later)
  - `get_or_create_cart(request)` — resolves guest-session vs user cart.
  - `add_item / update_qty / remove_item` — **re-check stock server-side** every time.
  - `merge_guest_cart_into_user(session_cart, user)` — called on login signal, sums
    quantities, drops out-of-stock lines.
  - `apply_coupon(cart, code)` — validate active/expiry/min-order/max-uses; store on
    cart. **Never** accept a discount amount from the client.
  - `price_cart(cart)` — returns line totals + subtotal + discount + shipping +
    grand total, **all recomputed from the DB**. This function is the single source of
    truth reused at checkout.
- Serializers: read-only computed totals; write serializers accept only
  `variant_id` + `quantity` + `coupon code`.
- Viewset: `/api/v1/cart/` (get), `items/` (add/patch/delete), `coupon/` (apply/remove).
  Ownership-scoped; guest carts bound to session, never addressable by ID.
- Wishlist: `Wishlist(user, variant)` unique-together; `/api/v1/wishlist/` list/toggle.
- Signal: hook allauth's `user_logged_in` → `merge_guest_cart_into_user`.

### Frontend
- `lib/api/cart.ts` + `lib/api/wishlist.ts` typed clients (send `X-CSRFToken`).
- Cart drawer/page: line items, qty stepper (optimistic, reconciled with server),
  coupon input, live totals from the server (never computed in JS).
- Wishlist: replace the current UI-only heart toggle with real persistence +
  optimistic update; `/account/wishlist` page.
- Cart badge count in the nav, hydrated from the server.

### Verify
- pytest: add-to-cart caps at stock, coupon rejects expired/over-limit, guest→user
  merge sums correctly, `price_cart` totals match hand-computed values, IDOR on
  another user's cart returns 404.

---

## Phase 7 — Orders & Payments (Razorpay) (`plan.md` §9, §10)

**Goal:** convert a priced cart into an immutable order, take payment via Razorpay,
and treat the **server-to-server webhook as the sole source of truth** for "paid".

### Backend — new `orders` app
- Models
  - `Order` — UUID pk + separate **non-guessable public `order_number`**, `user`,
    `status` enum (`created → payment_pending → paid → processing → shipped →
    delivered → cancelled → refunded`), snapshotted shipping address, **totals copied
    at creation** (never recomputed from live prices later — prices may change),
    `coupon_code` snapshot.
  - `OrderItem` — snapshot of variant name/sku/price/qty at purchase time (immutable
    record; don't FK-and-hope the product still exists).
  - State transitions live in `services.py` as an explicit guarded state machine
    (illegal transitions raise, e.g. can't ship an unpaid order).
- Checkout service
  1. `create_order_from_cart(cart)` — re-runs `cart.price_cart` server-side, snapshots
     everything, sets `payment_pending`, empties/locks the cart.
  2. Calls Razorpay Orders API **server-to-server** with the server-computed amount;
     stores `gateway_order_id`. Returns only the Razorpay order id to the client.
- **Payment app** (or `payments` module in orders)
  - `Payment` — gateway, `gateway_order_id`, `gateway_payment_id`, `signature`,
    `verified_at`, raw webhook payload (PII-scrubbed, for audit), `event_id` (dedup).
  - Client-callback endpoint: verifies HMAC-SHA256 signature but is **advisory only**
    (updates UI state, not order truth).
  - **Webhook endpoint** — the authoritative path:
    - Verify signature against the **raw, unparsed request body** with the separate
      webhook secret. Reject on mismatch (and log the failure — feeds §11 alerting).
    - **Idempotent**: dedup on Razorpay `event_id`; skip if already processed.
    - On `payment.captured`: inside a DB transaction with `select_for_update()`
      row-locks on the affected stock rows → decrement stock, flip order to `paid`,
      enqueue confirmation email + (if custom) the print job.
  - Needs ASGI/async-safe view or a sync webhook worker; keep the handler tiny and
    push work to Celery.

### Frontend
- Checkout page: address form (prefill from saved addresses), order summary from the
  server, "Pay" → Razorpay hosted checkout (no custom card form — keeps PCI scope at
  SAQ-A). On callback, poll order status (truth comes from the webhook, not the
  callback).
- `/account/orders` list + order-detail page reading snapshotted data.

### Verify
- pytest (highest blast radius — test hard):
  - webhook signature verification (valid/invalid/replayed),
  - idempotency (same `event_id` twice = one fulfilment),
  - **concurrent-payment race**: two payments against the last unit → exactly one
    succeeds (row-lock test),
  - illegal state transitions rejected,
  - totals on the order match the cart at creation time.
- Razorpay calls **mocked/recorded** — never live in CI.

---

## Phase 8 — Custom Design Orders → Qikink Print Fulfilment (`plan.md` §8, §10, §12)

**Goal:** accept a user-uploaded design safely, and only **after verified payment**
submit the print order to **Qikink** via their Open API, then **poll** Qikink for
status/tracking (Qikink has no outbound webhook — tracking is pull-based).

> **Provider decision:** the print partner is **Qikink** (India-based POD, Open API),
> not Printful/Printify. Custom orders flow: customer → our server (upload + validate)
> → payment verified → our server calls Qikink `order/create` → our beat task polls
> Qikink `order/status` → we surface tracking/AWB to the customer.

> **Delivery = dropshipping straight to the buyer (no double handling).** Qikink is a
> print-on-demand **dropshipping** service: the `shipping_address` we send in
> `order/create` is the **end customer's** delivery address (from the order snapshot,
> which is prefilled from the address they set at signup/checkout) — Qikink prints,
> packs **white-label under our brand**, and ships **directly to that customer's
> pincode** (29,000+ pincodes in India). It never comes to us; we never re-ship. We set
> `qikink_shipping = "1"` (Qikink runs the courier) and `gateway = "Prepaid"` (we
> already collected payment via Razorpay). Qikink's per-order shipping cost (weight/zone
> + 18% GST) is **our COGS**, absorbed into product margin — the customer is charged our
> simple flat ₹59 / free-over-₹999 rule (Phase 6). A future refinement could call
> Qikink's shipping calculator for exact fees; not needed for launch.

### Qikink API shape (from their Open API docs)
- **Base URLs:** sandbox `https://sandbox.qikink.com/`, live `https://api.qikink.com/`
  (live access requested in dashboard → Integration → Custom API). Both **base URL and
  each path are settings-configurable** so they can be corrected against the live
  Postman reference without code changes.
- **Auth:** `POST /api/token` with `ClientId` + `client_secret` (form) → `Accesstoken`.
  Cache the token in Redis with a TTL; every other call sends headers
  `ClientId: <id>` + `Accesstoken: <token>`.
- **Create order:** `POST /api/order/create` — body:
  `order_number` (our public order number), `qikink_shipping = "1"` (Qikink delivers to
  the customer), `gateway = "Prepaid"` (Razorpay already collected payment),
  `total_order_value`, `line_items[]` (`sku`, `print_type_id`, `quantity`, `price`,
  `designs[]` → `design_code`, `width_inches`, `height_inches`, `placement_sku`,
  `design_link` = short-lived signed URL to the uploaded art, `mockup_link`),
  and `shipping_address` = **the buyer's** delivery address (first/last name, address1/2,
  phone, email, city, zip, province, country_code) taken from the order snapshot.
- **Order status / tracking:** `GET /api/order/status` (id param) → returns Qikink
  status + AWB/tracking. Status vocabulary we map to our order state:
  `On Hold, Live OOS, Live, To be Printed, Partially Picklisted, Printed, Manifested,
  In-Transit, Exception, Delivered, RTO Initiated, Returned, Cancelled`.

### Backend — new `custom_orders` app
- `CustomDesignOrder` — links to an `Order` + chosen variant/placement/print type,
  object-storage **key** (not a public URL), `qikink_order_id`, `qikink_status`,
  `tracking_awb`/`tracking_link`, internal `review_status`
  (`auto_ok`|`flagged`|`approved`), and an `idempotency_key` (unique; our order number)
  so a retried submit never double-creates at Qikink.
- Upload handling (server-side, client validation is cosmetic only):
  - **Content-sniff the real MIME** (not the extension) via `filetype`, enforce max
    size/dimensions, **re-encode through Pillow** to strip EXIF and neutralise embedded
    payloads.
  - Store under a **randomised key in private object storage** (R2/S3 — see
    cross-cutting); Qikink receives only a **short-lived signed URL** as `design_link`.
  - Anything failing checks → `review_status=flagged` for manual eyeballing before it
    can reach Qikink (natural hook for later copyright/appropriateness review).
  - Create the `CustomDesignOrder` in `pending_payment`.
- **Submit (post-payment only):** triggered from the verified Razorpay webhook (§7) —
  a Celery task builds the Qikink payload (signed `design_link`, variant SKU, address
  snapshot) and calls `order/create` with our order number as the idempotency key;
  store the returned `qikink_order_id`, move the order to `processing`. `review_status
  != auto_ok/approved` short-circuits and never submits.
- **Status polling (no webhook):** a **Celery Beat** task periodically polls
  `order/status` for all open `CustomDesignOrder`s, maps the Qikink status onto our
  `Order` state machine (`Printed/Manifested → processing`, `In-Transit → shipped`,
  `Delivered → delivered`, `RTO*/Returned/Cancelled → cancelled/refunded`), stores the
  AWB/tracking, and enqueues a customer email on meaningful transitions. Backoff +
  give up polling once terminal.
- **SSRF/secrets guards:** Qikink calls go only to the configured Qikink host
  (allow-list); the `ClientId`/`client_secret` live server-side only, never sent to the
  browser; don't blindly follow redirects on Qikink responses.

### Frontend
- Custom-design option on the product page: client-side upload with preview + cosmetic
  validation, posts to **our** backend (never to Qikink — credentials stay server-side).
- Custom-order status + AWB/tracking visible in `/account/orders`.

### Verify
- pytest (Qikink HTTP **mocked** — never live in CI):
  - MIME-sniff rejects a renamed executable; oversized/over-dimension files rejected;
    EXIF stripped after re-encode.
  - idempotency key prevents a duplicate `order/create` on task retry.
  - `flagged` designs never auto-submit.
  - token is fetched once and reused from cache across calls.
  - status-poll mapping: each Qikink status maps to the expected internal order state.

---

## Phase 9 — Admin Hardening (`plan.md` §11)

*(No dependency on 6–8; can land in parallel. Must precede go-live.)*

- Admin already lives at an env-driven non-guessable path — add:
  - **IP allow-list / Zero-Trust** in front of that path at Caddy (or Cloudflare
    Access): unlisted IPs get a generic **404**, not a login page (don't confirm the
    admin exists to scanners).
  - **Require TOTP MFA** for every staff/superuser (allauth MFA); block staff login
    without it.
  - **Shorter session timeout** specifically for staff sessions.
  - `django-auditlog` for before/after field diffs on catalog/order/coupon changes,
    on top of Django's built-in `LogEntry`.
- Confirm `DEBUG=False` in prod excludes the debug toolbar/docs from the dependency
  set, not just the settings flag.

---

## Phase 10 — CI/CD & Security Scanning (`plan.md` §14)

*(Parallel with 6–8; must gate `main` before go-live.)*

- Extend `.github/workflows/ci.yml` beyond lint:
  lint → **typecheck** (mypy + tsc) → **unit tests** → **integration tests** against
  ephemeral Postgres/Redis services → build images → **Trivy** scan → push.
- **CodeQL** default setup (zero-config, auto-detects Python/JS).
- **Dependabot** weekly PRs for `uv`/`pip` + `npm`; security alerts on.
- **Secret scanning + push protection** at repo level.
- Add `pip-audit` / `npm audit` steps; pin lockfiles; pin container base images by
  digest.
- **Branch protection on `main`**: required passing CI (incl. CodeQL), required review,
  no direct pushes. Migrations as an explicit backward-compatible release step.

---

## Phase 11 — Observability (`plan.md` §16)

*(Best right after payments exist — money-in-limbo is the failure you most want to see.)*

- **Sentry** wired into both Django and Next.js.
- Health probes: keep `/healthz` (exists), add `/readyz` (checks DB/Redis/Meili),
  both excluded from auth + throttling.
- **Structured JSON logging** with a request/correlation ID threaded through Django →
  Celery tasks → Caddy logs, so one failed checkout traces end-to-end.
- **Alerting** specifically on: failed webhook-signature verifications, Celery task
  failure rate, and any payment/order-status mismatch.

---

## Phase 12 — Testing Breadth & Launch (`plan.md` §12, §15)

**The launch gate.** Nothing ships until this is green.

- Backend: broaden pytest with `factory_boy`/Faker fixtures; full coverage of the
  webhook, state machine, cart pricing, and search-sync signals (highest blast radius).
- Frontend: component tests (Vitest + RTL) + **Playwright E2E** on the critical paths —
  signup→login, search→add-to-cart→checkout happy path, custom-design upload.
- **k6 load test** on the search suggestion endpoint (the one endpoint built to be
  hammered) before launch.
- **axe** accessibility pass on key pages.
- Full walk of the **`plan.md` §12 security checklist**; **restore-test** the managed
  DB backups (an untested backup is not a backup).

---

## Cross-cutting (thread through the phases above)

- **Object storage (R2/S3)** wired for product media *and* custom-design uploads
  instead of local disk — a prerequisite for Phase 8, worth doing at the start of it.
- **Signup + password-reset UI** — allauth endpoints already exist; build the screens
  (login is done). Small, can land anytime.
- **Social-login credentials** (Google/Apple) — UI is built and env-gated; just needs
  keys when you want them live.
- **Email delivery** (order confirmation, shipping, password reset) — pick a provider
  (transactional email) and wire the Celery email tasks; needed by §7/§8.

---

## Suggested working order (concrete)

1. **Object storage** setup (unblocks §8, improves §4 media). *(cross-cutting)*
2. **Phase 6** cart + wishlist + coupons, with tests.
3. **Phase 7** orders + Razorpay + webhook (the core money path), with tests.
4. **Phase 11** observability — turn it on now that money flows.
5. **Phase 8** custom-print fulfilment, with tests.
6. **Phase 9** admin hardening + **Phase 10** CI security (can overlap steps 2–5).
7. **Signup/password-reset UI + email** somewhere alongside 2–3.
8. **Phase 12** full test + security pass → launch.

Each phase ends the same way the foundation slice did: `ruff`/`check`/`migrations`
clean, `pytest` green, frontend `tsc`/`next build` green, and `tasks.md` updated with
honest run status.

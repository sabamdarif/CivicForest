# CivicForest Security Bug-Fix Plan

**Source:** full-stack security audit of `backend/` (Django), `frontend/` (Next.js), `docker-compose.yml`, `.env`, `caddy/Caddyfile`.
**Goal:** close every HIGH/MEDIUM finding and the meaningful LOWs before public launch. The payment core (signature-verified webhook, server-side amounts, idempotent capture) is already sound and needs no changes — only its missing test coverage does.

**Decisions logged:**
- Checkout idempotency → `Idempotency-Key` header (see §2.3).
- Scope → all severities, step-by-step.
- Status → not yet public, so Phase 0 is the pre-deploy hardening gate that *blocks* launch.

---

## Phase 0 — Pre-deploy hardening gate (mandatory before any public deploy)

Nothing in this phase ships features; all of it must be done before the site is reachable from the internet. Current `.env` values are dev placeholders — treat them as compromised once any server exposes them.

### 0.1 Rotate every secret
Generate fresh values, **never** derive from the committed placeholders:
```
DJANGO_SECRET_KEY        → python -c "import secrets;print(secrets.token_urlsafe(50))"
POSTGRES_PASSWORD        → random 32+ chars (also update DATABASE_URL)
MEILISEARCH_MASTER_KEY   → random 32+ chars
RAZORPAY_KEY_ID/SECRET, RAZORPAY_WEBHOOK_SECRET → from Razorpay live dashboard (key_secret and webhook_secret are DIFFERENT values)
QIKINK_CLIENT_SECRET, EMAIL_HOST_PASSWORD, GOOGLE/APPLE_OAUTH_SECRET
```
Files: `.env` (git-ignored — edit in place), `.env.example` keeps placeholders only.
**Verify:** `git status` shows no `.env`; `docker compose config` resolves the new values.

### 0.2 Stop publishing databases/search on the host — `docker-compose.yml`
- Postgres (lines 35-36): **delete** the `ports: 5432:5432` block (backups/psql via `docker compose exec postgres psql`). If host access is ever needed, bind `"127.0.0.1:5432:5432"`.
- Meilisearch (line 51): same — delete or `"127.0.0.1:7700:7700"`, and flip `MEILI_ENV: production` (line 48).
**Verify:** from the host, `ss -tlnp` shows no `0.0.0.0:5432`/`0.0.0.0:7700`.

### 0.3 Production runtime profile
- Create `docker-compose.prod.yml` overriding the backend: `command: gunicorn config.wsgi:application -b 0.0.0.0:8000 --workers 3` (backend image must `pip install gunicorn` — add to `backend/requirements.txt`), with `DJANGO_SETTINGS_MODULE=config.settings.production` and `DJANGO_DEBUG=false` in a **separate `.env.production`** (never reuse the dev `.env`).
- Backend/worker/beat `volumes: ./backend:/app` mounts must NOT appear in prod compose (immutable image code).

### 0.4 Tighten admin + env hygiene
- `.env`: `ADMIN_IP_ALLOWLIST` currently `127.0.0.1/32 172.16.0.0/12` — replace the broad `172.16.0.0/12` with your office/VPN CIDR only.
- `.env.example:13`: keep the `DJANGO_ADMIN_PATH` key but with value `<generate-per-environment>`; generate a fresh path per environment (the path in `.env` must differ from the example and from any previously used value).
- `frontend/next.config.ts:27`: remove the `{ protocol: "http", hostname: "localhost" }` and `"backend"` remotePatterns from any config reachable in prod (gate them on `process.env.NODE_ENV !== "production"`).

**Phase 0 exit checklist:** all secrets rotated · no DB/search host ports · prod compose runs gunicorn + production settings · admin path + allowlist environment-specific.

---

## Phase 1 — HIGH severity fixes

### 1.1 Restore payment fulfilment test coverage
**Finding:** `backend/apps/payments/tests/conftest.py:39-48` — `capture_event()` builds the webhook entity without `amount`/`currency`, so every fulfilment test returns `amount_mismatch` and never exercises fulfil/stock/cart logic. The asserts at `test_webhook.py:57,74,101` currently fail against `services.py:118-129`.

**Fix — `backend/apps/payments/tests/conftest.py`:**
```python
def capture_event(
    gateway_order_id: str,
    payment_id: str = "pay_TEST",
    event_id: str = "evt_1",
    *,
    amount_paise: int,
    currency: str = "INR",
) -> bytes:
    return json.dumps({
        "id": event_id,
        "event": "payment.captured",
        "payload": {"payment": {"entity": {
            "id": payment_id,
            "order_id": gateway_order_id,
            "amount": amount_paise,
            "currency": currency,
        }}},
    }).encode()
```
**Fix — callers in `test_webhook.py`:** pass `amount_paise=gateway.to_paise(order.total)` (from `apps.payments.gateway`), `currency=order.currency` in all 4 tests. The `_order_with_payment` helper already returns the order; reassign at call sites (`order, payment, cart = ...`).
**Add one adverse test:** payload amount = 1 paise → response `"amount_mismatch"`, order stays `PAYMENT_PENDING`, stock untouched.
**Verify:** `cd backend && python -m pytest apps/payments -v` — all tests green; confirm via the adverse test that the amount gate still fires (prevents the fix from simply removing the check).

### 1.2 Idempotency guard on post-payment Qikink enqueue
**Finding:** `payments/services.py:146,156-168` — `_enqueue_post_payment` runs even when `fulfil_paid_order` short-circuits (already-paid order, distinct second capture event id) → duplicate print submissions billed twice.

**Fix — `backend/apps/payments/services.py`:** make `fulfil_paid_order` return a truthy "did we transition" signal (e.g. return `None` early at the `order.is_paid` branch, order otherwise) and enqueue only on a real transition:
```python
# orders/services.py:181  →  if order.is_paid: return None
# payments _handle_capture:
result = order_services.fulfil_paid_order(order, cart=cart)
...
if result is not None:            # only when this event actually paid the order
    _enqueue_post_payment(order)
```
(Alternatively, gate inside `_enqueue_post_payment` with `CustomDesignOrder.objects.filter(order=order, submit_status=PENDING_PAYMENT).exclude(submitted_at__isnull=False)` — the return-signal approach is simpler; keep ONE mechanism.)
**Verify:** new test — two `payment.captured` events with *different* event ids for the same order → `submit_custom_order_to_qikink.delay` called once total. Run `pytest apps/payments apps/orders`.

---

## Phase 2 — MEDIUM severity fixes

### 2.1 Frontend security headers — `frontend/next.config.ts`
Add a `headers()` block (no HTTP headers exist anywhere today):
```ts
async headers() {
  return [{
    source: "/:path*",
    headers: [
      { key: "X-Frame-Options", value: "DENY" },
      { key: "X-Content-Type-Options", value: "nosniff" },
      { key: "Referrer-Policy", value: "same-origin" },
      { key: "Permissions-Policy", value: "camera=(), microphone=(self), geolocation=()" },
      {
        key: "Content-Security-Policy",
        value: [
          "default-src 'self'",
          "script-src 'self' https://checkout.razorpay.com https://cdn.razorpay.com", // Next dev needs 'unsafe-eval' — keep prod tight
          "frame-src https://api.razorpay.com https://checkout.razorpay.com",
          `connect-src 'self' ${apiBase} https://lumberjack.razorpay.com`,
          `img-src 'self' data: https:`,
          "style-src 'self' 'unsafe-inline'",
        ].join("; "),
      },
    ],
  }];
}
```
Start with `Content-Security-Policy-Report-Only`, run through checkout + login e2e, then enforce. **Verify:** `curl -sI https://civicforest.local | grep -i -E 'csp|x-frame|nosniff'`; Playwright suite (`frontend/e2e/checkout.spec.ts`) passes with headers enforced.

### 2.2 Block absolute-URL credential leakage — `frontend/lib/api/client.ts:64`
```ts
const url = path.startsWith("http")
  ? (() => {
      const allowed = new URL(path);
      if (![new URL(PUBLIC_BASE).origin, new URL(INTERNAL_BASE).origin].includes(allowed.origin))
        throw new Error(`apiFetch: refusing credentials to ${allowed.origin}`);
      return path;
    })()
  : `${apiBase()}/api/v1${path}`;
```
**Verify:** unit-test or manual: `apiFetch("https://evil.example/x")` throws before any fetch.

### 2.3 Checkout idempotency (Idempotency-Key header)
**Backend:**
- `backend/apps/orders/models.py` — add `checkout_key = models.CharField(max_length=64, blank=True, null=True, unique=True, db_index=True)` (+ migration).
- `CheckoutView.post` (`orders/views.py:46`): read `request.headers.get("X-Idempotency-Key")` (validate `^[A-Za-z0-9_-]{8,64}$`, else 400). On hit: `Order.objects.filter(user=request.user, checkout_key=key, status=Order.Status.PAYMENT_PENDING).first()` → if found **and** a `Payment` row exists, return the *existing* order/payment payload (200, same shape as 201) — do NOT create a new Razorpay order. Otherwise save the new order with `checkout_key=key`.
- Requests without the header behave exactly as today (no regression).
**Frontend:** `frontend/app/(shop)/checkout/` — generate one key per cart contents (`crypto.randomUUID()`, memoised; regenerate on cart mutation) and send it on the checkout POST as `X-Idempotency-Key`.
**Note:** abandoned `payment_pending` orders still accumulate — acceptable short-term; a cleanup beat job is listed in Phase 3.
**Verify:** test — POST same key twice → one Order, one Payment row, second response returns the first order's identifiers.

### 2.4 Re-auth for OAuth-only users on address changes — `backend/apps/accounts/views.py:24-62`
`_require_recent_login` is a no-op for social-only accounts. Fix: in `AddressViewSet.perform_update/_destroy`, when `did_recently_authenticate` is False AND the user `has_usable_password()` is False, require re-auth via the OAuth re-login flow (frontend redirect to `/account/reauthenticate` which kicks the Google flow) — i.e. explicitly handle the OAuth-only branch instead of silently passing. Also apply the check to `perform_create` for consistency (create currently skips it).
**Verify:** tests — OAuth-only user (set unusable password) updating an address without recent auth → 4xx; password user with recent login → success.

### 2.5 `/readyz` exposure — `backend/config/urls.py:20-43`
Move `/readyz` and `/healthz` behind a cheap guard: either require a shared-secret header (`X-Health-Token`, env-configured; Caddy strips it publicly and only internal healthcheck carries it) or bind them to an `internal` DRF throttle; document that the *public* Caddyfile should 404 `/readyz` (the compose Caddyfile already proxies selectively — add the deny there).
**Verify:** public `curl https://api.../readyz` → 404/401 without the token; compose healthcheck with token → 200.

### 2.6 Auth gate fail-open — `frontend/proxy.ts:45`
Change the catch branch from `NextResponse.next()` to a safe holding page: `NextResponse.rewrite(new URL("/maintenance", req.url))` for `/account/*` (create a tiny static `app/maintenance/page.tsx`); `/login`,`/signup` may still pass through (they're safe anonymously). **Do not** redirect-loop: only gate the protected section.
**Verify:** kill the backend (`docker compose stop backend`), hit `/account/orders` → maintenance page, never the account UI.

### 2.7 Throttle order/checkout endpoints — `backend/config/settings/base.py`
Add DRF scoped rates and attach to views:
```python
"DEFAULT_THROTTLE_RATES": { ..., "checkout": "10/min", "checkout_day": "60/day",
                            "custom_order_create": "20/hour" }
```
- `CheckoutView.throttle_classes = [ScopedRateThrottle]`, `throttle_scope = "checkout"` (plus a secondary day-scoped class for `checkout_day`).
- `CustomDesignViewSet.create` → scope `custom_order_create` (protects the Pillow CPU-bomb vector).
**Verify:** `pytest` new tests — 11th checkout POST in a minute → 429.

---

## Phase 3 — LOW severity hardening

| # | Fix | File | Change |
|---|-----|------|--------|
| 3.1 | `tracking_link` scheme validation | `custom_orders/services.py:138-147`, serializers | `urlsplit(link).scheme in {"http","https"}` else store `""`; frontend (`app/(account)/account/orders/[order_number]/page.tsx:121`) renders the link only after the same check |
| 3.2 | `verify_callback` zero-row return | `payments/services.py:49-55` | capture `updated = ...update(...)`; return `updated > 0`; view 404s on False |
| 3.3 | Guest session rotation on login | `accounts` login signal (next to `merge_guest_cart_into_user`) | call `request.session.cycle_key()` after merge so a fixated pre-login id dies |
| 3.4 | Stop storing raw session keys | `search/views.py:71-76` | store `sha256(session_key)` (or drop the column); add a retention note/cleanup for `SearchQueryLog` |
| 3.5 | `transition()` TOCTOU | `orders/services.py:42-54` | wrap in `select_for_update` re-read of `order.status` before validating (atomic) |
| 3.6 | Cart-clearing removes re-added items | `orders/services.py:209-215` | delete by exact `CartItem` ids snapshotted at checkout (store ids on the order/Payment meta) instead of `variant_id__in` |
| 3.7 | e2e secret hygiene | `config/settings/e2e.py`, `frontend/playwright.config.ts` | assert at import in `e2e.py` that `DJANGO_SETTINGS_MODULE` endswith `.e2e` (fail loudly otherwise) so those hardcoded fake secrets can never serve prod |
| 3.8 | `X-Request-ID` echo bound | `apps/common/middleware.py:38-43` | validate `^[A-Za-z0-9-]{1,64}$`, replace invalid chars |
| 3.9 | Swagger outside DEBUG | `config/urls.py:61-71` | gate on `DEBUG` only (already true) — confirm prod compose guarantees `DEBUG=false`; no code change, checklist item |
| 3.10 | Missing allauth rate limits | `base.py:172-176` | add allauth rate keys: `manage_email: 5/5m/key`, `change_password: 5/5m/key`, tighten TOTP `authenticate` |

---

## Execution & verification order

1. **Phase 1 first** (code + tests): `cd backend && python -m pytest apps/payments apps/custom_orders -v` must be fully green — this is the regression gate for the money path.
2. **Phase 2** with targeted new tests (throttle 429s, idempotency, apiFetch guard, address re-auth), then the Playwright e2e suite (`cd frontend && npx playwright test`) with CSP enforced.
3. **Phase 3** in one pass with a single backend pytest run.
4. **Phase 0 last, immediately before launch** (rotating secrets early is wasted work; do it at deploy time). Gate = the Phase 0 exit checklist above.

## Out of scope / explicitly not broken (do not "fix")
Webhook HMAC verification, server-side pricing, upload sanitisation, IDOR scoping, cookie flags, Argon2, allauth enumeration handling, XSS surface — audited and clean; changes here risk regressions for no gain.

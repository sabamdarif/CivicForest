# 03: Target architecture

---

## 1. Repository layout after the rebuild

The `backend/` directory is flattened to the repo root so Vercel's zero-config detection finds
`manage.py` without an entrypoint override, and so `STATIC_ROOT`/`collectstatic` behave by default.

```
CivicForest/
├── manage.py
├── pyproject.toml                 # deps + [tool.vercel] + [tool.ruff] + [tool.pytest]
├── uv.lock
├── vercel.json                    # functions.maxDuration, headers, crons
├── config/
│   ├── settings/
│   │   ├── base.py                # everything shared
│   │   ├── local.py               # SQLite fallback, console email, DEBUG
│   │   ├── production.py          # Neon, R2, Resend, security headers
│   │   └── test.py                # fast hashers, eager jobs, fake gateways
│   ├── urls.py                    # public + account + custom + api + admin + hooks + cron
│   ├── wsgi.py                    # the Vercel entrypoint (ASGI intentionally absent)
│   └── jinja2.py                  # Jinja2 environment factory: globals, filters, tests
├── apps/
│   ├── common/                    # base models, mixins, pagination, jobs, email, R2 helpers
│   ├── accounts/                  # User, Address, profile views
│   ├── catalog/                   # Category, Collection, Product, Variant, Image, Size, Color, Material, Tag, SizeChart
│   ├── cart/                      # Cart, CartItem, Coupon, Wishlist, pricing service
│   ├── orders/                    # Order, OrderItem, Shipment, StatusEvent, Return
│   ├── payments/                  # Payment, WebhookEvent, Razorpay gateway
│   ├── custom_orders/             # CustomBlank, DesignUpload, CustomDesignOrder, Qikink client
│   ├── reviews/                   # Review, FitFeedback, moderation
│   ├── content/                   # Page, FaqEntry, AnnouncementBar, HomeSection, ContactMessage
│   ├── search/                    # rebuilt: search document, synonyms, suggest endpoint, query log
│   └── backoffice/                # the custom staff pages (views + templates only, no models)
├── templates/
│   ├── jinja2/                    # every customer-facing and back-office page
│   └── django/                    # allauth overrides + Django admin overrides (DTL only)
├── static/
│   ├── css/                       # tokens.css, base.css, and one sheet per page area
│   ├── js/                        # one ES module per interactive feature
│   └── fonts/                     # self-hosted woff2 subsets
├── designs/                       # reference screenshots (unchanged)
└── rebuild/                       # these documents
```

Deleted: `frontend/`, `caddy/`, `docker-compose.yml`, `docker-compose.prod.yml`,
`config/celery.py`, `k6-search-suggest.js`, `Makefile` (replaced by `pyproject` scripts),
`.env.render`, `django-allauth/` (installed from PyPI at a pinned version instead).

---

## 2. Settings and configuration

Four modules under `config/settings/`. `base.py` holds everything shared and reads all secrets from
the environment through `django-environ`; nothing branches on `DEBUG` for security behaviour.

### Environment variables

| Variable | Purpose | Required |
|---|---|---|
| `DJANGO_SETTINGS_MODULE` | `config.settings.production` on Vercel | yes |
| `DJANGO_SECRET_KEY` | signing key; production refuses to boot on the dev default | yes |
| `DJANGO_DEBUG` | `False` in production | yes |
| `DJANGO_ALLOWED_HOSTS` | `civicforest.com,www.civicforest.com,.vercel.app` | yes |
| `CSRF_TRUSTED_ORIGINS` | `https://civicforest.com,https://*.vercel.app` | yes |
| `DATABASE_URL` | Neon pooled connection string | yes |
| `S3_ENDPOINT_URL` `S3_ACCESS_KEY_ID` `S3_SECRET_ACCESS_KEY` `S3_BUCKET_NAME` `S3_REGION` | R2 public bucket | yes |
| `S3_PRIVATE_BUCKET_NAME` | R2 private bucket for raw and print-ready design files | yes |
| `R2_PUBLIC_BASE_URL` | CDN hostname for the public bucket | yes |
| `RESEND_API_KEY` `DEFAULT_FROM_EMAIL` `SUPPORT_EMAIL` | transactional email | yes |
| `RAZORPAY_KEY_ID` `RAZORPAY_KEY_SECRET` `RAZORPAY_WEBHOOK_SECRET` | payments; webhook secret is separate from the API secret | yes |
| `RAZORPAY_FAKE_MODE` | test/e2e only, never set in production | no |
| `QIKINK_CLIENT_ID` `QIKINK_CLIENT_SECRET` `QIKINK_BASE_URL` | POD fulfilment; base URL switches sandbox ↔ live | yes |
| `QIKINK_TOKEN_PATH` `QIKINK_ORDER_CREATE_PATH` `QIKINK_ORDER_STATUS_PATH` `QIKINK_TOKEN_TTL` | overridable paths so a Qikink API change needs no deploy | no |
| `GOOGLE_OAUTH_CLIENT_ID` `GOOGLE_OAUTH_CLIENT_SECRET` | social login | yes |
| `DJANGO_ADMIN_URL` | non-guessable admin path, e.g. `manage-a91f3c/` | yes |
| `BACKOFFICE_URL` | path prefix for the custom staff pages | yes |
| `CRON_SECRET` | bearer token every cron endpoint requires | yes |
| `HEALTH_CHECK_TOKEN` | guards `/healthz` detail | yes |
| `SHIPPING_FLAT_RATE` `FREE_SHIPPING_THRESHOLD` `CURRENCY` | 79 / 999 / INR | yes |
| `DEFAULT_TAX_RATE` `DEFAULT_HSN_CODE` | fallbacks when a product has none | yes |
| `RETURN_WINDOW_DAYS` | 7 | yes |
| `SENTRY_DSN` `SENTRY_ENVIRONMENT` `SENTRY_TRACES_SAMPLE_RATE` | observability | no |
| `GA4_MEASUREMENT_ID` | analytics | no |
| `STAFF_SESSION_AGE` | 3600 | no |
| `MAINTENANCE_MODE` | serves the branded maintenance page | no |
| `USE_SQLITE` | local development only | no |

### Non-obvious settings

- `WSGI_APPLICATION = "config.wsgi.application"` and **no `ASGI_APPLICATION`**: Vercel prefers ASGI
  when both exist, and nothing here needs async. `config/asgi.py` is deleted.
- `STORAGES` uses `django-storages` S3 backend for `default` (media) and
  `ManifestStaticFilesStorage` for `staticfiles`. `STATIC_ROOT` is set so Vercel's automatic
  `collectstatic` works; no build script calls it.
- `SECURE_HSTS_SECONDS`, `SECURE_SSL_REDIRECT`, `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE`,
  `X_FRAME_OPTIONS = "DENY"`, `SECURE_CONTENT_TYPE_NOSNIFF`, `SECURE_REFERRER_POLICY` and a strict CSP
  are on in production. `django-cors-headers` is **removed**: there is no cross-origin frontend.
- Argon2id password hashing is kept.

---

## 3. Two template engines, and why

django-allauth ships Django Template Language templates and template tags. Jinja2 cannot render them.
Both engines are registered; the split is by ownership, not by page type:

| Engine | Directory | Renders |
|---|---|---|
| Jinja2 | `templates/jinja2/` | Every page CivicForest owns: storefront, account area, custom line, back-office, emails |
| DTL | `templates/django/` | allauth's ~25 auth templates and Django admin overrides |

Both extend a shell that pulls in the same `tokens.css` and `base.css`, so the login page in the
screenshot looks identical to the rest of the site despite a different engine rendering it.
`templates/django/allauth/layouts/base.html` is overridden once to inherit the site chrome, which
means individual allauth templates mostly need no override at all.

`config/jinja2.py` builds the environment with:

- **Globals:** `static`, `url` (wrapping `reverse`), `now`, `settings_flag`, `csrf_input`,
  `announcement`, `nav_categories`, `cart_summary`, `is_staff`.
- **Filters:** `rupees` (₹1,23,456.00 Indian digit grouping), `paise`, `pct_off`, `date_in`
  (dd Mmm yyyy), `timesince_in`, `pluralise_in`, `image_url` (R2 key → CDN URL at a given width),
  `srcset`, `markdown_safe`, `order_status_label`, `json_ld`.
- **Tests:** `in_stock`, `on_sale`, `custom_item`.
- `autoescape=True`, `undefined=StrictUndefined` in local and test so a typo in a variable name fails
  loudly instead of rendering nothing.
- Jinja2 bytecode cache into `/tmp`: the only writable path on Vercel, and it survives within a warm
  function instance.

Context processors do not exist in Jinja2. Anything a template needs globally comes from the
environment globals above, each a callable that resolves lazily from the request via a
`ContextVar` set by middleware, so `cart_summary()` costs nothing on pages that never call it.

---

## 4. URL map

```
/                                    home
/shop/                               product grid, all filters as query params
/shop/<category-slug>/               category-scoped grid
/collections/                        collection index
/collections/<slug>/                 one collection
/product/<slug>/                     product detail
/search/                             search results
/customise/                          custom line landing
/customise/<blank-slug>/             the design tool for one blank
/cart/                               cart page
/checkout/                           login-gated; address → summary → pay
/checkout/complete/<order_number>/   thank-you, idempotent, safe to reload
/about/  /contact/  /faq/  /size-guide/  /sustainability/
/shipping-delivery/  /returns-exchanges/  /privacy/  /terms/  /grievance-redressal/
/track/                              guest order tracking by number + email
/account/                            dashboard
/account/orders/  /account/orders/<order_number>/
/account/orders/<order_number>/invoice/
/account/orders/<order_number>/return/
/account/returns/  /account/wishlist/  /account/addresses/  /account/profile/
/account/designs/                    saved artwork, reorderable
/account/security/                   2FA setup, sessions, recovery codes
/account/data/                       export or deletion request
/accounts/…                          allauth: login, signup, logout, password, email, 2FA, Google
/api/v1/…                            internal JSON for the site's own JS (session + CSRF)
/hooks/razorpay/                     signed webhook
/internal/cron/<job-name>/           bearer-token cron endpoints
/healthz/  /sitemap.xml  /robots.txt
/<BACKOFFICE_URL>/…                  custom staff pages
/<DJANGO_ADMIN_URL>/                 hardened Django admin
```

---

## 5. Data model

### Kept unchanged

`common.UUIDTimestampedModel` (UUID pk + timestamps, so nothing customer-facing is enumerable),
`accounts.User` (email login, no username, UUID pk, `marketing_opt_in`), `accounts.Address`,
`catalog.{Material,Size,Color,Category,Tag,Product,ProductVariant,ProductImage}`,
`cart.{Cart,CartItem,Coupon,Wishlist}`, `orders.{Order,OrderItem}`,
`payments.{Payment,WebhookEvent}`, `custom_orders.CustomDesignOrder`.

### Changed

| Model | Change | Why |
|---|---|---|
| `Product` | + `mrp`, `country_of_origin`, `hsn_code`, `tax_rate`, `care_instructions`, `fit_notes`, `model_note`, `gsm`, `weight_grams`, `length_cm`, `width_cm`, `height_cm`, `collections` M2M | C2, C3, C10 and courier data |
| `ProductVariant` | + `low_stock_threshold`, `qikink_sku` (blank for stock-only products) | A6 alerts, F11 mapping |
| `ProductImage` | `image` becomes an R2 key; + `width_variants` JSON of generated widths | A1 |
| `Coupon` | + `per_user_limit`, `scope_categories`, `scope_products`, `first_order_only`, `exclude_sale_items`, `starts_at`, `free_shipping` | J2. **`per_user_limit` is the gap that makes the current coupon abusable** |
| `Order` | + `fulfilment_kind` (stock / custom / mixed), `tax_total`, `place_of_supply`, `invoice_number`, `invoice_date`, `cancelled_at`, `cancel_reason`, `rights_ack_text` | Split fulfilment, GST invoice, cancellation |
| `OrderItem` | + `tax_rate`, `tax_amount`, `hsn_code`, `mrp_at_purchase` | Snapshotted for the invoice; tax must never be recomputed from live product data |
| `CustomDesignOrder` | + `blank_variant` FK, `design_upload` FK, `back_placement` fields, `print_surcharge`, `qikink_last_polled_at`, `retry_count`, `last_error` | F2, F7, F12 |

### New

| Model | Fields | Purpose |
|---|---|---|
| `catalog.Collection` | name, slug, tagline, description, hero image, display order, is_active | C7: curated groups with their own copy |
| `catalog.SizeChart` | category FK, rows JSON, notes, unit | C11 |
| `orders.Shipment` | order FK, kind (stock/custom), carrier, awb, tracking_url, shipped_at, delivered_at, items M2M | One order, two shipments (decision #10) |
| `orders.StatusEvent` | order FK, from_status, to_status, actor, note, created_at | Customer timeline and staff audit in one place |
| `orders.ReturnRequest` | order FK, items M2M, reason, comment, photos, status, resolution, refund_amount, received_at | I4 |
| `custom_orders.CustomBlank` | product-like: name, slug, base price, print areas, images, Qikink product mapping, is_active | The six blanks, kept out of the stock catalogue |
| `custom_orders.DesignUpload` | user FK (nullable for guests), r2_key_raw, r2_key_print, mime, bytes, width_px, height_px, dpi_estimate, status, sanitised_at, review_status, review_reason | Upload is separate from the order so one design can be reused |
| `reviews.Review` | product FK, user FK, order_item FK (proves purchase), rating, title, body, fit_feedback, status, published_at | K1, K4, K5 |
| `content.Page` | slug, title, body, meta fields, is_published | L2 |
| `content.FaqEntry` | question, answer, category, display order | N3 |
| `content.AnnouncementBar` | text, url, is_active, starts_at, ends_at | D14 |
| `content.HomeSection` | kind, title, subtitle, image, target, display order, is_active | Editable homepage |
| `content.ContactMessage` | name, email, order_number, subject, message, handled_by, handled_at, internal_note | N1, N2 |
| `content.NewsletterSubscriber` | email, confirmed_at, unsubscribed_at, source | J5, double opt-in |
| `common.JobRun` | name, key, status, payload JSON, attempts, next_attempt_at, last_error, started_at, finished_at | The whole deferred-work system (§7) |
| `common.StockAdjustment` | variant FK, delta, reason, actor, note | O6: stock changes are never silent |
| `common.OutboundEmail` | to, template, context JSON, status, provider_id, error, sent_at | Resend/retry any email from the admin; proof of what was sent |

---

## 6. Two fulfilment paths in one order

A cart may hold stock items and custom items (decision #10). One `Order`, one Razorpay payment, and
`Order.fulfilment_kind` records which case it is. On payment verification the order fans out into
`Shipment` rows: one per kind:

```
Order CF-7Q3KX9AR  (mixed, ₹2,847)
├── Shipment #1  kind=stock   → staff pack → carrier + AWB typed in admin
│     └── OrderItem  Classic Black Tee / M / Black
└── Shipment #2  kind=custom  → Qikink order → AWB polled from Qikink
      └── OrderItem  Custom Hoodie / L / Forest  ←→ CustomDesignOrder
```

Rules this forces, all of which are explicit in the code rather than implied:

- Order status is **derived** from its shipments, never set by hand: any shipped and any not →
  `partially_shipped`; all shipped → `shipped`; all delivered → `delivered`.
- The customer's order page shows two timelines with two tracking numbers, labelled by what they are
  ("Shipped by CivicForest", "Printed and shipped by Qikink"), because delivery dates will differ.
- Shipping is charged **once** on the order, not per shipment.
- Cancellation is per shipment: the stock shipment can be cancelled until it is marked shipped; the
  custom shipment cannot be cancelled once Qikink has accepted it.
- Returns are per shipment with **different policies**: a 7-day return on stock items, defect-only with
  an unboxing video on custom items. The returns page states both, per line.
- The shipped email is sent per shipment, so a customer gets two, each naming what is inside it.

---

## 7. Deferred work without a queue

`common.JobRun` is the whole system. A job is a row, not a process.

```python
JobRun(name="qikink.submit", key=f"cdo:{design_order.pk}", payload={...})
```

- `key` is unique per logical unit of work, so enqueueing twice is a no-op. This is the idempotency
  guarantee that replaces a broker's deduplication.
- A handler registry maps `name` → callable. Handlers are pure functions of `payload` and must be
  safe to run twice.
- `status`: pending → running → done, or failed with `attempts`, `last_error` and `next_attempt_at`
  set by exponential backoff (1 min, 5 min, 30 min, 2 h, 6 h, then dead-letter).
- Every job carries a `run_now` button in the back-office and shows its full error text. A dead-letter
  row raises an admin alert rather than sitting silently.

Trigger surfaces, in order of preference:

1. **Event-driven inline**: fast, must-be-immediate work runs in the request: sending the order
   confirmation email, creating the Razorpay order. Wrapped so a third-party failure downgrades to a
   `JobRun` instead of failing the customer's request.
2. **Cron endpoints**: `POST /internal/cron/<job-name>/` with `Authorization: Bearer $CRON_SECRET`,
   declared in `vercel.json`. Each drains a bounded batch inside the function time limit and reports
   what it did.
3. **On-demand piggyback**: when a customer opens an order page whose custom shipment was last polled
   over 30 minutes ago, poll Qikink inline. **This is what makes Hobby's once-a-day cron survivable**
   (decision #3): the data a customer is actually looking at is fresh even when the sweep is not.

Cron schedule (Pro cadence; on Hobby each collapses to daily and the piggyback carries the load):

| Job | Pro schedule | Purpose |
|---|---|---|
| `qikink.poll` | every 15 min | status and AWB for open custom shipments |
| `jobs.retry` | every 5 min | drain pending and retryable `JobRun` rows |
| `designs.sanitise` | every 5 min | pull raw uploads from R2, validate, re-encode, write print-ready file |
| `email.drain` | every 5 min | retry failed `OutboundEmail` rows |
| `cart.abandoned` | hourly | one email per cart, four hours after last change |
| `search.reindex` | every 30 min | refresh stale `SearchDocument` rows |
| `stock.low` | daily 09:00 IST | low-stock digest to staff |
| `coupons.expire` | daily 00:15 IST | deactivate expired coupons |
| `payments.reconcile` | daily 02:00 IST | compare Razorpay settlements against `Payment` rows |
| `housekeeping` | daily 03:00 IST | expire carts, prune sessions, prune search logs, prune job rows |

---

## 8. Media on R2

Two buckets, because product photography and customer artwork have opposite access requirements.

| Bucket | Access | Contents | Key shape |
|---|---|---|---|
| `civicforest-media` | Public, behind a CDN hostname | product and collection imagery, homepage art, generated widths, static files from `collectstatic` | `products/<uuid>/<width>.webp` |
| `civicforest-designs` | **Private**, no public read | raw customer uploads, sanitised print-ready PNGs, generated mockups | `designs/raw/<uuid>.bin`, `designs/print/<uuid>.png` |

- Product images: the admin uploads once; a job generates 400 / 800 / 1600 px WebP plus a JPEG
  fallback and records the keys. Templates ask for a width and get a CDN URL.
- Design files are **never** publicly readable. Qikink receives a presigned GET valid for 24 hours,
  long enough for them to fetch it and short enough to be useless if leaked.
- Raw uploads are deleted once sanitisation succeeds. Only the re-encoded PNG is retained.
- Filenames are always random UUIDs, never the customer's original filename, that is both an
  enumeration guard and a stored-XSS guard.

## 9. Payment flow, precisely

```
cart  ──POST /api/v1/checkout/──►  re-price server-side, snapshot, Order(payment_pending)
                                   Razorpay order created, id returned
browser ──Razorpay modal──► Razorpay ──► browser callback ──POST /api/v1/payments/verify/──►
                                                              HMAC check → Payment(captured)
Razorpay ──webhook──► /hooks/razorpay/ ──► HMAC check → dedupe on WebhookEvent → fulfil
```

The webhook is the authoritative path; the browser callback only makes the thank-you page fast. Both
funnel into one idempotent `fulfil_order()` guarded by the order's status, so whichever arrives first
wins and the second is a no-op. `RAZORPAY_FAKE_MODE` lets tests sign their own webhooks locally.

## 10. Frontend system

### CSS

```
static/css/
├── tokens.css      custom properties: colour, type scale, spacing, radii, shadow, z-index, motion
├── base.css        reset, elements, focus rings, container, grid/stack utilities, .sr-only
├── components.css  button, field, badge, card, accordion, modal, drawer, toast, breadcrumb,
│                   pagination, stepper, price, swatch, rating, empty state, skeleton
├── layout.css      header, nav, footer, announcement bar
├── shop.css        grid, filters, sort, pagination
├── product.css     gallery, buy panel, accordions, size chart
├── cart.css        cart page and drawer
├── checkout.css    checkout and thank-you
├── account.css     account area and auth pages (shared with the DTL allauth templates)
├── designer.css    the custom design tool
├── backoffice.css  dense tables, dashboard tiles, forms
└── print.css       invoice and packing slip
```

Every page loads `tokens`, `base`, `components`, `layout` plus at most one page sheet. No CSS-in-JS,
no utility framework, no preprocessor, no build step, `ManifestStaticFilesStorage` hashes the files
and the CDN serves them.

### JavaScript

One module per behaviour, each self-initialising from a `data-` attribute so a template opts in by
markup rather than by script tag:

```
static/js/
├── util.js            fetch wrapper with CSRF, rupee formatter, debounce, focus trap
├── nav.js  modal.js  toast.js
├── filters.js         URL-param sync, fetch-and-replace grid, chip removal
├── search-overlay.js  debounced suggest, keyboard nav, aria-live
├── gallery.js  variant-picker.js  pincode.js  recently-viewed.js
├── cart.js            add/update/remove, drawer render, header count
├── wishlist.js  checkout.js  designer.js
└── backoffice.js      table filters, bulk select, inline stock edit, sparkline render
```

**The contract:** every one of these enhances markup that already works. Filters are a `<form>` that
submits. Add-to-cart is a `<form>` that posts and redirects. The design tool is the single exception
and tells the customer so if JavaScript is unavailable.

---

## 11. Template inventory

`templates/jinja2/`: 58 files, grouped:

| Group | Templates |
|---|---|
| Shell | `base.html`, `_partials/{header,footer,announcement,icons,search_overlay,cart_drawer,toast,cookie_banner,trust_strip}.html` |
| Macros | `_macros/{icon,button,field,card,badge,price,swatch,rating,accordion,modal,stepper,empty,breadcrumbs,pagination}.html` |
| Storefront | `home.html`, `shop/{list,_grid,_filters,_sort,_filter_drawer}.html`, `collections/{index,detail}.html`, `product/{detail,_gallery,_buy_panel,_accordions,_size_chart,_related}.html`, `search/{results,_zero}.html` |
| Custom line | `customise/{landing,designer,_blank_card,_upload_panel,_placement_tabs}.html` |
| Cart & checkout | `cart/{page,_lines,_summary,_coupon,_progress}.html`, `checkout/{page,_address,_summary,complete}.html` |
| Account | `account/{dashboard,orders,order_detail,invoice,returns,return_form,wishlist,addresses,address_form,profile,security,designs,data}.html` |
| Content | `content/{page,faq,contact,track,size_guide,grievance}.html`, `errors/{404,500,maintenance}.html` |
| Back-office | `backoffice/{dashboard,orders,order_detail,shipments,products,product_form,variants,inventory,coupons,customers,returns,designs,content,jobs,reports,styleguide}.html` |
| Email | `email/{base,order_confirmation,payment_failed,shipped,delivered,cancelled,refunded,return_received,return_resolved,design_approved,design_rejected,abandoned_cart,review_request,welcome,newsletter_confirm}.{html,txt}` |
| Print | `print/{invoice,packing_slip}.html` |

`templates/django/`: allauth overrides only: `allauth/layouts/base.html` (the one that matters, since
every other allauth page extends it), plus styled versions of `account/login.html`,
`account/signup.html`, `account/password_reset.html`, `account/email.html`, `mfa/*.html`, and
`socialaccount/*.html`. Plus `admin/base_site.html` and `admin/index.html`.

---

## 12. Security controls

| Risk | Control | Status |
|---|---|---|
| Price or total tampering | Every total recomputed server-side from the database; the client sends only ids, quantities and a coupon code | Exists, kept |
| Coupon abuse | Server-side validation plus `per_user_limit`, scope and date window | **Gap today: added** |
| Oversell | `select_for_update` on variants inside the fulfilment transaction; revalidation at cart view and checkout | Strengthened |
| Webhook replay | HMAC verification + unique `(gateway, event_id)` ledger | Exists, kept |
| Duplicate Qikink print jobs | Unique `idempotency_key` per custom line, checked before submit | Exists, kept |
| Malicious upload | Content-sniff, Pillow verify, dimension cap, full re-encode, random filename, private bucket, no public read | Exists, moved off the request path |
| SSRF via Qikink config | Request host pinned to the configured Qikink hostname | Exists, kept |
| IDOR | Every queryset scoped to `request.user`; UUID pks; random order numbers | Exists, kept |
| Admin discovery | Path from env, never `/admin/`; TOTP mandatory for staff; 1 h session | Kept, DEBUG bypass removed |
| Enumeration of orders | Random `CF-` order numbers; guest tracking requires number **and** matching email, rate-limited | Kept |
| CSRF | Django CSRF on every mutating request including the JSON endpoints; `SameSite=Lax`; no CORS | Simplified: same-origin now |
| XSS | Jinja2 autoescaping on; no `|safe` on user content; page bodies sanitised on save; strict CSP without `unsafe-inline` | New CSP |
| Brute force | allauth rate limits plus DRF throttles on auth, search, coupon and upload-token endpoints | Kept |
| Secret leakage | Everything from env; no secret in a template or a JS module; upload tokens are short-lived and user-scoped | Kept |
| Dependency risk | `pip-audit` and CodeQL in CI, Dependabot on | Kept |
| Data at rest | Neon encryption; PII limited to what shipping requires; no card data ever touches the app | Kept |

---

## 13. Compliance, implemented

Each legal requirement from `02-research.md` §5 maps to a concrete artefact, so compliance is
verifiable by reading code rather than by assertion.

| Requirement | Where it lives |
|---|---|
| Total price with full breakdown before commitment | `price_cart` returns subtotal, discount, shipping, tax and total; the cart and checkout summaries render every line; nothing is added after the terms checkbox |
| Country of origin per product | `Product.country_of_origin`, required in the admin form, rendered in the product accordions and on the invoice |
| Return / refund / exchange policy | `/returns-exchanges/` plus a per-line policy note on the product page, differing for stock and custom |
| Delivery timelines | Pincode estimate on the product page, SLA on the shipping page, per-shipment estimate on the order |
| Seller identity and contact | Footer, contact page, invoice header |
| Named grievance officer with timelines | `/grievance-redressal/`, linked in the footer |
| No pre-ticked consent | Newsletter, marketing opt-in and terms all default to unticked; a test asserts this |
| No drip pricing | Shipping and tax are shown in the cart before login, let alone before payment |
| No false urgency | Low-stock messaging is derived from `stock_quantity` and `low_stock_threshold`; there is no countdown component in the codebase at all |
| Equal-prominence decline | Shared button macro; secondary variant is the same size, not greyed into invisibility |
| One-click unsubscribe | Signed token link in every marketing email; no login required |
| GST invoice fields | `print/invoice.html` renders HSN, description, quantity with UQC, taxable value, rate, tax amount, place of supply and seller identity from snapshotted `OrderItem` fields |
| DPDP consent and rights | `User.marketing_opt_in`, `/privacy/`, `/account/data/` for export and deletion requests |

## 14. Observability

Sentry for exceptions and traces with a scrubbed `before_send`. JSON logs with a request id, no PII.
`/healthz/` returns database, R2 and job-queue health, detail gated behind `HEALTH_CHECK_TOKEN`. The
back-office jobs panel is the operational dashboard: pending, failed and dead-lettered counts, oldest
pending age, and last-success time per cron job. An external monitor pings `/healthz/` every five
minutes because Vercel keeps only one hour of runtime logs on Hobby.

## 15. Testing strategy

| Layer | Tool | What it covers |
|---|---|---|
| Unit | pytest | pricing, coupon rules, tax, status machine, Qikink payload shape, upload sanitisation, search ranking |
| Integration | pytest + Django test client | full checkout, webhook handling, cart merge on login, stock decrement under contention, job retry and dead-letter |
| Template | pytest | every page renders for guest, customer and staff; no `StrictUndefined` failures |
| Adversarial | pytest | tampered totals, replayed webhooks, coupon reuse, IDOR on another user's order, oversized and disguised uploads, unauthorised cron calls |
| End-to-end | Playwright | signup and login; search → cart → checkout → signed webhook → fulfilment; custom design upload |
| Accessibility | axe | nine key pages |
| Budget | CI script | CSS and JS byte size per page |

Test settings use fast password hashers, `RAZORPAY_FAKE_MODE`, a fake Qikink transport, `locmem`
email, and jobs executed synchronously so a test can assert on their effects.

---

## 16. Deployment

`pyproject.toml`:

```toml
[tool.vercel]
# Optional once backend/ is flattened: Vercel finds config/wsgi.py from WSGI_APPLICATION.
entrypoint = "config.wsgi:application"

[tool.vercel.scripts]
# collectstatic runs automatically; this is only for anything else the build needs.
build = "python build.py"
```

`vercel.json`:

```json
{
  "$schema": "https://openapi.vercel.sh/vercel.json",
  "functions": { "config/wsgi.py": { "maxDuration": 60 } },
  "crons": [
    { "path": "/internal/cron/jobs.retry/",        "schedule": "*/5 * * * *" },
    { "path": "/internal/cron/designs.sanitise/",  "schedule": "*/5 * * * *" },
    { "path": "/internal/cron/email.drain/",       "schedule": "*/5 * * * *" },
    { "path": "/internal/cron/qikink.poll/",       "schedule": "*/15 * * * *" },
    { "path": "/internal/cron/search.reindex/",    "schedule": "*/30 * * * *" },
    { "path": "/internal/cron/cart.abandoned/",    "schedule": "17 * * * *" },
    { "path": "/internal/cron/stock.low/",         "schedule": "30 3 * * *" },
    { "path": "/internal/cron/coupons.expire/",    "schedule": "15 18 * * *" },
    { "path": "/internal/cron/payments.reconcile/","schedule": "30 20 * * *" },
    { "path": "/internal/cron/housekeeping/",      "schedule": "30 21 * * *" }
  ]
}
```

Times are UTC; the daily entries above land at 09:00, 00:15, 02:00 and 03:00 IST. **On Hobby only the
daily entries deploy**: the sub-daily ones fail the build, so they are commented out until the Pro
upgrade, and the on-demand piggyback (§7) covers the gap.

Release procedure, deliberately manual at the migration step:

1. Push to a branch → Vercel builds a preview against the Neon preview branch.
2. Review the preview. CI must be green.
3. Run `migrate` against production from a local shell with `vercel env pull`. Migrations stay
   backward-compatible so the currently-live function keeps working during the window.
4. Promote the deployment.
5. Verify `/healthz/`, place a test order in Razorpay test mode, check the jobs panel.

Rollback: promote the previous deployment. Because migrations are additive and backward-compatible, no
database rollback is needed, which is the whole reason for that constraint.

---

## 17. What actually changes, file by file

| Current | Fate |
|---|---|
| `backend/apps/{accounts,catalog,cart,orders,payments,custom_orders}/models.py`, `services.py`, `tests/` | **Kept**, extended per §5 |
| `backend/apps/*/serializers.py`, `views.py`, `urls.py` | Rewritten: DRF stays, but for internal same-origin JSON, not a public API |
| `backend/apps/*/admin.py` | Rewritten as hardened `ModelAdmin`s beneath the new back-office |
| `backend/apps/search/` | Deleted and rebuilt on Postgres |
| `backend/apps/common/{tasks.py}` | Replaced by the `JobRun` system |
| `backend/apps/common/{email.py,pagination.py,throttles.py,exceptions.py,middleware.py,factories.py}` | Kept, adapted |
| `backend/config/settings/*` | Rewritten |
| `backend/config/{celery.py,asgi.py}` | Deleted |
| `backend/templates/admin/*` | Kept as a starting point for the admin overrides |
| `frontend/` | Deleted: brand imagery in `frontend/public/brand/` copied to `static/img/` first |
| `caddy/`, `docker-compose*.yml`, `Makefile`, `k6-search-suggest.js`, `.env.render` | Deleted |
| `django-allauth/` | Deleted; installed from PyPI at `==65.19.1` |
| `plan.md`, `implementation_plan.md`, `tasks.md`, `remaining_plan.md`, `bug_fix_plan.md` | Moved to `rebuild/legacy/` |
| `designs/` | Kept as visual reference |


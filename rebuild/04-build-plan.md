# 04: Build plan

Ordered milestones. Everything ships before launch (decision #16), so these are internal gates, not
public releases. Each milestone lists its tasks, the files it touches, and what has to be true before
the next one starts.

Sequencing principle: **platform first, then money path, then everything that hangs off it.** The
riskiest unknowns (Vercel deployment shape, R2 direct upload, Qikink sandbox) are pulled early so a
surprise there doesn't invalidate finished work.

---

## Milestone map

| # | Milestone | Why here | Rough size |
|---|---|---|---|
| M0 | Demolition and skeleton | Nothing can be verified until one deployable Django project exists on Vercel | S |
| M1 | Design system foundation | Every later template depends on tokens, layout primitives and the header/footer | M |
| M2 | Catalogue and browse | The data everything else references | L |
| M3 | Search | Depends on catalogue; needed by header on every page | M |
| M4 | Cart | Depends on catalogue; gates checkout | M |
| M5 | Auth and account area | Needed before checkout because checkout is gated | M |
| M6 | Checkout, payments, orders | The money path. Highest risk, so it gets a whole milestone | L |
| M7 | Custom design line and Qikink | Depends on cart, checkout, R2 upload and the job system | L |
| M8 | Back-office | Depends on every model existing | L |
| M9 | Reviews, returns, content, compliance, polish | Fills in the remaining surface | L |
| M10 | Hardening and launch | Tests, budgets, compliance sign-off, DNS cutover | M |

Dependency graph:

```
M0 ──► M1 ──► M2 ──┬─► M3 ──┐
                   ├─► M4 ──┤
                   │        ├─► M6 ──┬─► M7 ──┐
             M5 ───┴────────┘        │        ├─► M10
                                     └─► M8 ──┤
                                        M9 ───┘
```

---

## M0: Demolition and skeleton

**Goal:** a single Django project at the repo root that deploys to Vercel, serves one styled page,
connects to Neon, and can write to R2.

Tasks:

1. [x] Branch `rebuild/foundation`. Tag the current `main` as `v1-nextjs` so the old stack is recoverable.
2. [x] Delete `frontend/`, `caddy/`, `docker-compose.yml`, `docker-compose.prod.yml`, `config/celery.py`,
   `apps/search/`, `k6-search-suggest.js`, `Makefile`, `.env.render`, `django-allauth/`.
3. [x] Move everything from `backend/` to the repo root. Fix `pyproject.toml` paths, `manage.py`,
   `DJANGO_SETTINGS_MODULE` references and the pytest config.
4. [x] Rewrite `pyproject.toml`: drop `celery`, `django-celery-beat`, `meilisearch`, `redis`,
   `django-cors-headers`, `gunicorn`, `uvicorn`. Add `django-allauth[socialaccount,mfa]==65.19.1`,
   `resend`, `jinja2`. Add `[tool.vercel]` and `[tool.vercel.scripts]`.
5. [x] Delete `config/asgi.py`; keep `config/wsgi.py` as the sole entrypoint.
6. [x] Rewrite the four `config/settings/` modules (`base`, `local`, `production`, `test`) per
   `03-architecture.md` §2.
   Delete `e2e.py` and fold its fake-gateway switches into `test.py`.
7. [x] Add `config/jinja2.py` and register both template engines.
8. [x] Create `templates/jinja2/base.html` and `templates/django/base.html` sharing one stylesheet.
9. [ ] Provision Neon, create the `main` and `preview` branches, set `DATABASE_URL`. Run migrations.
10. [ ] Provision two R2 buckets (public `civicforest-media`, private `civicforest-designs`), an API
    token, and a public CDN hostname. Verify a `collectstatic` upload and a signed private read.
11. [ ] Create the Vercel project, set all environment variables, deploy, confirm the styled page renders
    with CDN-served static files.
12. [ ] Add `vercel.json` with `functions.maxDuration`, security headers and an empty `crons` array.
13. [x] Rewrite `.github/workflows/ci.yml`: ruff → pytest against Postgres → `pip-audit`. Keep
    `codeql.yml` and `dependabot.yml`.
14. [x] Rewrite `README.md` for the new stack. Move the old plan documents into `rebuild/legacy/`.

**Done when:** a pushed commit auto-deploys, `/` renders a styled page, `/healthz` returns 200,
migrations are applied on Neon, static files come from the CDN, and CI is green.

---

## M1: Design system foundation

**Goal:** the visual language and shared chrome every later page inherits, extracted from the seven
reference screenshots.

Tasks:

1. [x] `static/css/tokens.css`: colour (near-black `#0d0d0d`, gold `#c9a227`, cream `#f7f4ef`, ink,
   muted, success, danger), type scale, spacing scale, radii, shadows, container widths, z-index
   layers, transition durations. All as custom properties on `:root`.
2. [x] Self-host the two typefaces as subset `woff2` with `font-display: swap`: a serif display face for
   headings, a humanist sans for body. Record the licence for each in `static/fonts/LICENCE.md`.
3. [x] `static/css/base.css`: reset, element defaults, focus-visible rings, `prefers-reduced-motion`
   guard, `.container`, grid and stack utilities, `.sr-only`.
4. [x] `templates/jinja2/_partials/icons.html`, the sprite inlined once per page because an external
   `<use href>` only resolves same-origin: search, account, cart, heart, close, chevrons,
   plus/minus, trash, truck, shield, leaf, headset, star, upload, check, filter, social icons.
5. [x] Component CSS + Jinja2 macros: button (primary/secondary/ghost, 3 sizes), form field with label,
   help and error states, badge, card, accordion, modal, drawer, toast, breadcrumb, pagination,
   quantity stepper, price display (MRP strike-through + percentage off), swatch, star rating,
   empty state, skeleton.
6. [x] `templates/jinja2/_partials/header.html`: logo, five nav items plus CUSTOMISE, search trigger,
   account link, cart button with live count. Sticky, with a mobile drawer.
7. [x] `templates/jinja2/_partials/footer.html`: the four link columns from the screenshots (Shop,
   Collections, Customer Care, About Us), newsletter form, social row, legal row.
8. [x] Announcement bar partial, driven by the `AnnouncementBar` model.
9. [x] Shared behaviours: `static/js/nav.js`, `toast.js`, `modal.js` (which drives the drawer too).
   No `drawer.js` or `accordion.js`: `<dialog>` and `<details name>` already do their work.
10. [ ] A `/styleguide/` page (staff-only) rendering every component in every state. This is the
    regression surface for CSS work and the reference for the back-office pages.

**Done when:** the styleguide renders correctly at 360 / 768 / 1280 px, keyboard focus is visible
throughout, axe reports no violations on it, and total CSS is under 60 KB uncompressed.

---

## M2: Catalogue and browse

**Goal:** every page a visitor can reach without an account, driven by real data.

Tasks:

1. Migrate `apps/catalog`: add `Collection`, `SizeChart`, and to `Product` add `mrp`,
   `country_of_origin`, `hsn_code`, `tax_rate`, `care_instructions`, `fit_notes`, `model_note`,
   `gsm`, `weight_grams`, `length_cm`/`width_cm`/`height_cm`. Add `Product.collections` M2M.
2. Add `ProductImage` variants: store the R2 key plus generated widths; `alt_text` becomes required
   at the form level.
3. Services: `product_list(filters, sort, page)` returning products, facet counts and total in one
   query pass; `facet_counts(queryset)`; `related_products(product)`; `price_display(variant)`.
4. Home page: hero, four-icon trust strip, shop-by-category tiles, "Just Landed" row, brand values
   band, newsletter: sections ordered and toggled by the `HomeSection` model.
5. Shop page: grid, sidebar filters with counts, sort select, numbered pagination, mobile filter
   drawer, active-filter chips with individual removal, empty state.
6. Collections index and detail.
7. Product detail: gallery with hover zoom and lightbox, colour swatches that swap images, size
   buttons with out-of-stock struck through, price with MRP and percentage off, wishlist heart,
   quantity stepper, add-to-cart, accordions (description / fabric and care / shipping and returns),
   size-chart modal, pincode delivery estimate, trust strip, related products, breadcrumbs.
8. JSON-LD: `Product` + `Offer` + `AggregateRating` on detail, `BreadcrumbList` on all,
   `Organization` + `WebSite` on home.
9. `static/js/`: `filters.js`, `gallery.js`, `variant-picker.js`, `wishlist.js`, `pincode.js`,
   `recently-viewed.js`.
10. `seed_catalog` command rewritten for the new fields, using the brand imagery in
    `frontend/public/brand/`: copy those PNGs to `static/img/seed/` before deleting `frontend/`.
11. Sitemap covering products, categories, collections and static pages.

**Done when:** a visitor can browse from home to a product page and back through every filter and
sort combination **with JavaScript disabled**, facet counts are correct, LCP on the shop page is
under 2.5 s on a throttled connection, and Rich Results Test validates the product markup.

---

## M3: Search

**Goal:** typo-tolerant search and autocomplete on Postgres alone.

Tasks:

1. Rebuild `apps/search` with no Meilisearch: `SearchDocument` (one row per product, `SearchVectorField`
   with a GIN index, plus a plain text blob for trigram), `SearchSynonym` (admin-editable term →
   expansion), keep `SearchQueryLog`.
2. Weighted document: name `A`, category and collection `B`, tags and material `C`, description `D`.
3. Rebuild triggers: `post_save`/`post_delete` on Product, Variant, Category, Collection, Tag mark the
   document stale; a cron sweep refreshes stale rows in batches. Never rebuild inline in a request.
4. Query path: exact prefix → full-text rank → trigram similarity fallback at 0.3, unioned and
   deduplicated. Synonyms expanded before the query is built.
5. `/api/v1/search/suggest/`: products with thumbnails, matching categories, popular queries. Capped,
   throttled, cached 60 s.
6. `/search/` results page reusing the shop grid, filters and sorts, with the query echoed as in the
   screenshot ("You searched for 'hoodie'").
7. Zero-result page: "did you mean" from trigram, popular products, and the term logged.
8. `static/js/search-overlay.js`: 250 ms debounce, arrow-key navigation, Escape to close, `aria-live`
   result count, works as a plain form submit if JS fails.
9. `reindex_search` management command for a full rebuild.

**Done when:** "hoodei" finds hoodies, "tshirt" and "t-shirt" and "tee" all match via synonyms,
suggestions return in under 150 ms warm, and the results page is identical in behaviour to the shop
grid.

---

## M4: Cart

**Goal:** a guest can fill a cart, price it correctly, and be stopped only at checkout.

Tasks:

1. Keep `cart/services.py` (`price_cart`, `merge_guest_cart_into_user`, quantity validation) and
   extend `price_cart` to compute tax per line from the product's HSN rate and to return a full
   breakdown (subtotal, discount, shipping, tax, total) rather than a total alone.
2. Extend `Coupon` with `per_user_limit`, scope fields, `first_order_only`, `exclude_sale_items`,
   `starts_at`, `free_shipping`. Add redemption counting per user. **This closes a real abuse hole in
   the current model, which counts only global uses.**
3. Cart page: line rows with image, variant, price, stepper, remove, move-to-wishlist; order summary
   with the breakdown; coupon field with inline validation; free-shipping progress bar with the exact
   shortfall; cross-sell row; empty state.
4. Cart drawer, opened by add-to-cart and by the header button, sharing one partial with the page.
5. `/api/v1/cart/` endpoints: add, update quantity, remove, apply coupon, remove coupon, summary.
   Every one re-prices server-side and returns the authoritative totals; the client never sends money.
6. Wishlist: heart toggle on cards and product pages, `/account/wishlist/` page, move-to-cart. For a
   guest the heart prompts login rather than storing a cookie wishlist. That is an assumed default, flagged in
   `01-decisions.md`.
7. `static/js/cart.js`: optimistic quantity updates that reconcile against the server response,
   drawer rendering, toast on add, header count sync.
8. Stock revalidation on cart view with a message naming the affected line.
9. Cron: abandoned-cart sweep, cart expiry sweep.

**Done when:** prices, discounts, tax and shipping are computed only server-side; a tampered payload
cannot change a total; a guest cart survives login with quantities merged rather than overwritten;
and every coupon rule has a test.

---

## M5: Auth and the account area

**Goal:** allauth wired in, the login screen from the screenshot rendered, the account area complete.

Tasks:

1. Install `django-allauth[socialaccount,mfa]==65.19.1` from PyPI; delete the vendored checkout.
2. Configure: email-only login, mandatory verification by link, Argon2, rate limits, Google provider,
   `MFA_SUPPORTED_TYPES = ["recovery_codes", "totp"]`, `MFA_TOTP_ISSUER = "CivicForest"`,
   `MFA_TRUST_ENABLED = True` with a 14-day cookie.
3. Override `templates/django/allauth/layouts/base.html` once so every allauth page inherits the site
   chrome, then style the specific pages: login, signup, logout, password reset and change, email
   management, 2FA activate/deactivate/authenticate, recovery codes, social signup.
4. Build the login page to match the screenshot: split layout, brand imagery left, form right, email
   and password fields with icons, show/hide password toggle, remember me, forgot-password link,
   "Continue with Google", link to signup, and the four-icon trust strip beneath. Apple is deferred
   (B4): the button is not rendered rather than rendered dead.
5. Checkout gate: `/checkout/` requires login and redirects with `?next=`, and the login page shows a
   contextual line explaining why. On success, merge the guest cart and continue to checkout.
6. Account area: dashboard, orders list and detail, invoice view, addresses CRUD with a default,
   profile with marketing opt-in (unticked), security page (2FA setup with QR, recovery codes,
   active sessions), saved designs, data export/deletion request.
7. Staff gate: mandatory TOTP for `is_staff`, 1 h session, obscure admin path. **Remove the DEBUG
   bypass currently in `StaffAdminMiddleware`.** Add a real TOTP setup page so the first superuser no
   longer needs a shell snippet: this is a documented pain point in the current README.
8. Emails: welcome, verification, password reset, email change, 2FA enabled/disabled.

**Done when:** signup → verify → login → 2FA enrol → logout → login with TOTP all work; Google login
creates a verified account; an unauthenticated visit to `/checkout/` returns to checkout with the cart
intact; and no staff user can reach the admin without TOTP.

---

## M6: Checkout, payments, orders

**Goal:** money moves correctly, and it is impossible for a customer to pay the wrong amount.

Tasks:

1. Extend `Order`, `OrderItem` per `03-architecture.md` §5. Add `Shipment` and `StatusEvent`.
2. Rewrite `orders/services.py`: `create_order_from_cart` re-prices from scratch, snapshots every
   line with unit price, MRP, tax rate, tax amount and HSN, computes place of supply from the shipping
   state, and takes an immutable address copy: all inside one transaction.
3. Checkout page: contact, shipping address (saved-address picker plus new-address form), pincode
   autofill and estimate, billing-address toggle, order summary with the full breakdown, coupon field,
   terms checkbox, pay button.
4. Razorpay: create gateway order → open the Standard Checkout modal → verify signature server-side →
   transition the order. Keep `RAZORPAY_FAKE_MODE` for tests.
5. Webhook at `/hooks/razorpay/`: verify HMAC, dedupe on `WebhookEvent`, and treat it as the
   **authoritative** confirmation: the browser callback is a convenience, not proof.
6. On payment verified, in one transaction: decrement stock with `select_for_update`, create shipments,
   increment coupon usage, mark the cart converted, enqueue the confirmation email and any Qikink
   submissions.
7. Order status machine with allowed transitions only, every change writing a `StatusEvent`.
8. Failed payment: retry from order detail for 24 h, then a job cancels and releases stock.
9. Thank-you page keyed on order number, idempotent, safe to reload or bookmark.
10. Invoice: GST-compliant HTML at `/account/orders/<n>/invoice/`, sequential numbering per financial
    year, print stylesheet, HSN and rate per line, tax summary, place of supply, seller identity.
11. Order history and detail with two timelines, per-shipment tracking, and cancel where allowed.
12. `/track/` guest lookup by order number + email, rate-limited to 5/min per IP.
13. Emails: order confirmation, payment failed, shipped (per shipment), delivered, cancelled, refunded.
14. Tests: tampered totals rejected · coupon reuse past `per_user_limit` rejected · concurrent checkout
    of the last unit oversells zero · replayed webhook processed once · signature mismatch rejected ·
    stock released on auto-cancel.

**Done when:** a real Razorpay test payment completes end to end, a signed replayed webhook changes
nothing on the second delivery, two concurrent checkouts for one remaining unit produce exactly one
paid order, and the invoice carries every field GST requires.

---

## M7: Custom design line and Qikink

**Goal:** a customer uploads artwork, sees it on the garment, buys it, and Qikink prints and ships it.

Tasks:

1. Models: `CustomBlank` with per-blank print areas in inches and pixel offsets for preview,
   `DesignUpload`, and the `CustomDesignOrder` extensions.
2. R2 direct upload: `POST /api/v1/designs/upload-url/` authenticates the user, validates the declared
   content type and size, and returns a presigned PUT valid for 5 minutes into the **private** bucket
   under a random key. The browser uploads directly. **Django never receives the bytes**. That is mandatory,
   because the Vercel body cap is 4.5 MB and print artwork exceeds it.
3. `designs.sanitise` job: fetch from R2 into `/tmp`, content-sniff the real MIME with `filetype`,
   `Image.verify()`, cap dimensions, estimate effective DPI against the requested print size, re-encode
   to a clean PNG stripping EXIF and ICC, write the print-ready file back to R2, delete the raw file.
   This is the existing `uploads.py` logic moved out of the request path.
4. `/customise/` landing: the six blanks, how it works, pricing, turnaround, the defect-only return
   policy stated plainly.
5. The design tool (`static/js/designer.js`, ~400 lines, no dependencies): upload or pick a saved
   design, front/back tabs, drag and pinch to position, scale handles clamped to the print area,
   dashed print-area outline, live price as print size changes, a resolution warning when the raster is
   too small, colour and size selection, add to cart. Serialises to placement SKU, width and height in
   inches: exactly Qikink's fields.
6. Moderation queue in the back-office: artwork at full resolution, approve or reject with a reason,
   customer emailed either way.
7. `qikink.submit` job: build the payload with **strings** for `quantity`, `price` and
   `total_order_value` and a **number** for `search_from_my_products`; `order_number` ≤ 15 characters;
   signed URLs for design and mockup; idempotent on `idempotency_key`; only after payment is verified
   **and** review has passed.
8. `qikink.poll` job plus the 30-minute on-demand piggyback on order views; map Qikink statuses to
   shipment statuses; store AWB and tracking link.
9. Failure path: alert staff, back off, expose a manual resubmit, never fail silently.
10. `/account/designs/`: saved artwork, reorder, delete.
11. Rights acknowledgement checkbox, wording snapshotted onto the order.
12. Sandbox verification before go-live: `search_from_my_products: 0` with hand-supplied design fields,
    because sandbox cannot see live dashboard products. Record the real print type IDs and placement
    SKUs from your dashboard's Postman collection into `02-research.md` §3 as you find them.

**Done when:** a design survives upload → sanitise → preview → cart → pay → review → Qikink sandbox
order → polled status, a resubmit after a forced failure creates no duplicate print job, and the
preview matches the printed placement within the tolerance Qikink states.

---

## M8: Back-office

**Goal:** the store can be run entirely from the browser, by someone who is not a developer.

Tasks:

1. `apps/backoffice`: views and templates only, no models. Everything behind a
   `StaffRequiredMixin` that enforces `is_staff` **and** a confirmed TOTP authenticator, plus a
   per-view permission check.
2. Four Django groups with explicit permissions: Owner, Manager, Fulfilment, Support (decision O11),
   created by a `bootstrap_roles` management command so they are reproducible, not hand-clicked.
3. Dashboard: the fifteen tiles from O1, a 30-day revenue sparkline and a status bar chart, both
   hand-rolled inline SVG. Every tile links to the filtered list behind it.
4. Order queue: filters, saved views ("awaiting dispatch", "custom pending review", "payment failed"),
   bulk selection, CSV export streamed rather than buffered (the 4.5 MB response cap).
5. Order detail: both timelines, per-shipment carrier and AWB entry, guarded transitions, cancel,
   refund, resend any email, internal notes, packing slip and invoice print views.
6. Design review queue (built in M7, surfaced here alongside everything else).
7. Product management: list with inline stock and price editing, full form with variant matrix,
   drag-reorder images, duplicate, archive, CSV import with a dry-run diff before committing.
8. Inventory: stock-on-hand report, adjustment form that always records a reason into
   `StockAdjustment`, low-stock list with thresholds.
9. Coupons: CRUD plus a usage report per coupon and per customer.
10. Customers: list, detail with orders and lifetime value, block, CSV export.
11. Returns queue: approve, reject, mark received, trigger refund.
12. Content: pages, announcement bar, homepage sections, FAQ entries, category and collection imagery.
13. Jobs panel: `JobRun` rows by status, full error text, "run now" per job and per row, dead-letter
    alerts. `OutboundEmail` list with resend.
14. Reports: sales by day, product and category; GST summary by rate; coupon performance; inventory
    valuation; zero-result search terms. Each exportable.
15. Django admin hardening underneath: obscure URL from env, TOTP required, 1 h session,
    `django-auditlog` on every model, read-only fields for money, no bulk delete on orders.
16. A real TOTP enrolment page so bootstrapping the first staff account needs no shell.

**Done when:** a non-developer can take an order from paid to delivered, add a product with variants
and images, issue a refund, review a design, fix a policy page and read yesterday's revenue without
touching Django admin, and every one of those actions appears in the audit log.

---

## M9: Reviews, returns, content, compliance

**Goal:** everything left on the customer-facing surface.

Tasks:

1. `apps/reviews`: `Review` tied to an `OrderItem` so only verified purchasers can write one, star
   rating, title, body, fit feedback, moderation status. Aggregate rating cached on the product and
   recomputed on publish.
2. Review UI: form reachable from order detail and from the review-request email, list on the product
   page with distribution bars, aggregated fit feedback ("72% say true to size"), `AggregateRating`
   markup, moderation queue in the back-office.
3. Returns: request form with reason, comment and photo upload (direct to R2), eligibility computed
   from delivery date and the 7-day window, **different rules for stock and custom lines**, admin
   queue, refund trigger, customer emails at each transition.
4. `apps/content`: `Page`, `FaqEntry`, `AnnouncementBar`, `HomeSection`, `ContactMessage`,
   `NewsletterSubscriber`, all editable in the back-office.
5. Write the twelve content pages. Returns & Exchanges must state both policies side by side, and the
   custom-line policy must reflect Qikink's actual terms (defect-only,
   7 days, unboxing video, no size swap), not a softer promise you cannot fund.
6. Grievance Redressal page: named officer, email, phone, postal address, response timeline.
7. Contact form with honeypot and rate limit; support inbox in the back-office.
8. Newsletter: double opt-in, welcome code issued only after confirmation, one-click unsubscribe.
9. Cookie banner gating GA4; analytics does not load before consent.
10. SEO pass: meta on every page, OG images, canonicals, `sitemap.xml`, `robots.txt`, all JSON-LD.
11. Compliance sweep against `02-research.md` §5: walk the entire journey logged in and logged out
    looking for pre-ticked boxes, charges that appear late, urgency claims that are not true, and
    decline paths that are harder than accept paths.
12. Branded 404, 500 and maintenance pages.

**Done when:** the compliance sweep is clean, every policy page matches what the system actually does,
and a review cannot be posted by someone who did not buy the product.

---

## M10: Hardening and launch

Tasks:

1. Test suite to target: unit, integration, and the three Playwright flows green in CI.
2. axe pass on home, shop, product, cart, checkout, login, account, customise, contact.
3. Performance: Lighthouse on the five heaviest pages, CSS and JS size budgets enforced in CI, image
   dimensions everywhere, fonts preloaded, LCP under 2.5 s.
4. Load check: the search-suggest and shop-list endpoints under sustained concurrency, p95 under
   500 ms.
5. Security review: `manage.py check --deploy` clean, CSP without `unsafe-inline`, secret scan, a
   deliberate attempt to tamper with a total and to replay a webhook.
6. Restore rehearsal: take a `pg_dump`, restore it to a scratch Neon branch, confirm the site runs.
7. Switch Qikink from sandbox to live and place one real low-value custom order end to end.
8. Switch Razorpay to live keys, register the production webhook, place one real low-value order,
   refund it.
9. SPF, DKIM and DMARC on the sending domain; send one of each template to Gmail, Outlook and a
   corporate mailbox and check placement.
10. Upgrade to Vercel Pro, move the crons from daily to their real cadence, confirm each fires.
11. Seed the real catalogue; delete all demo data; verify no seeded product survives.
12. DNS cutover: apex plus `www` redirect, HSTS on, certificate confirmed.
13. Post-launch watch: Sentry, the jobs panel and the failed-payment tile checked daily for the first
    week.

**Done when:** a real customer can buy a real product and a real custom print, both arrive, and every
email, invoice and tracking link along the way was correct.

---

## Risk register

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Qikink's undocumented API differs from the payload derived from third-party reports | High | Blocks M7 | Verify against your dashboard's Postman collection **first thing in M7**, before building the design tool on top of assumptions. The client is already settings-driven so paths change without a deploy |
| Qikink sandbox cannot see live products, so `search_from_my_products: 1` fails there | Confirmed | Wasted debugging | Use `0` with hand-supplied design fields in sandbox; flip to `1` only against live |
| Print placement preview does not match the printed result | Medium | Customer complaints, and under Qikink's terms the reprint is **your** cost | Order physical test prints of each blank and placement before launch. Qikink themselves recommend buying swatches first |
| 4.5 MB body cap discovered late | Eliminated | n/a | Direct-to-R2 upload is in the design from M7 task 2, not retrofitted |
| Hobby crons make tracking look broken | Medium | Support load | The 30-minute on-demand piggyback means the customer-visible data is fresh regardless. Upgrade at launch |
| Cold starts on a single Vercel function | Medium | Slow first paint | Fluid compute keeps instances warm under traffic; keep the bundle lean and defer imports of Pillow and boto3 into the functions that need them |
| Postgres search proves too weak as the catalogue grows | Low at this size | Poor search | The synonym table and trigram threshold are tunable; the query layer is isolated behind `search/services.py` so swapping in a hosted engine later touches one module |
| Neon connection exhaustion from many short-lived function instances | Medium | 500s under load | Use the pooled connection string, `CONN_MAX_AGE = 0`, and keep transactions short |
| Two fulfilment paths create status confusion | Medium | Wrong emails, wrong expectations | Order status is derived from shipments, never set directly; per-shipment emails name what is inside |
| Dark-pattern exposure from a well-meaning UI touch | Low | ₹10 lakh first violation | The compliance sweep in M9 task 11, plus tests asserting consent defaults are unticked |
| Apparel GST slabs are not what any blog says | High | Wrong invoices | Rate and HSN are per-product configuration, and your CA confirms the numbers before M10 |
| Losing the old implementation while demolishing | Low | Rework | Tag `v1-nextjs` before deleting anything; the old plan documents move to `rebuild/legacy/` rather than being deleted |

---

## Post-launch backlog

In rough value order, all deliberately excluded from launch (`01-decisions.md` Part 4): cash on
delivery · size exchange with reverse logistics · guest checkout · back-in-stock notifications ·
review photo uploads · Apple sign-in · WhatsApp order updates · a courier API for automatic AWB and
tracking · loyalty points · referrals · gift cards · Hindi translation · a blog for organic search.

---

## Using this document

Milestones are checklists, not estimates: tick tasks in place as they land. When a decision changes
mid-build, edit `01-decisions.md` first and note the milestone affected, so the register never drifts
from what was actually built. When something is learned about Qikink's real API, write it into
`02-research.md` §3 immediately; that section is the only record of an API with no public
documentation.


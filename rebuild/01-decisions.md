# 01: Decision register

Three parts: **confirmed** decisions the owner made explicitly, **assumed** decisions taken as the
recommended default and open to veto, and **non-goals** deliberately excluded.

---

## Part 1: Confirmed decisions

| # | Area | Decision | Consequence |
|---|---|---|---|
| 1 | Stack | Django + DRF, Jinja2 for all pages, vanilla CSS + vanilla JS, django-allauth, single Vercel deployment | Not open for debate. No React, no Tailwind, no bundler, no second host |
| 2 | Starting point | Keep `backend/apps/{catalog,cart,orders,payments,custom_orders,accounts}` models, services and tests. Rewrite every view, serializer, URL, template, stylesheet and script. Delete `frontend/`, `docker-compose*.yml`, `caddy/`, `config/celery.py`, `apps/search` | The proven money-path logic: server-side re-pricing, webhook idempotency, upload sanitisation, cart merge, UUID PKs, carries over instead of being re-derived |
| 3 | Hosting | Vercel **Hobby now, Pro at launch**. Cron-dependent features designed for Pro cadence, degraded but functional on Hobby's once-a-day crons | Every scheduled job also gets an on-demand trigger so nothing is blocked before the upgrade |
| 4 | Database | Neon Postgres. Branch-per-preview-deployment | Serverless-friendly pooling; free tier covers development |
| 5 | Object storage | Cloudflare R2, S3-compatible via `django-storages` | Zero egress fees on an image-heavy catalogue; existing storage settings work unchanged |
| 6 | Search | Postgres full-text (`SearchVector`/`SearchRank`) + `pg_trgm` similarity + admin-editable synonyms | No second datastore, nothing to keep in sync, no reindex outage. `apps/search` (Meilisearch) is deleted |
| 7 | Deferred work | Inline for fast third-party calls; anything that can fail becomes a database job row swept by token-protected cron endpoints with backoff. Every job has a manual "run now" | No Celery, no Redis, no queue billing. Fully inspectable and retryable from the admin |
| 8 | Catalogue fulfilment | Stock-fulfilled and shipped by CivicForest | Inventory, oversell protection and low-stock alerts are all in scope |
| 9 | Custom fulfilment | A separate **CUSTOMISE** line on Qikink blanks, printed and dropshipped by Qikink | Two fulfilment paths, two return policies, two tracking sources |
| 10 | Custom line placement | Own top-level nav item between SHOP and COLLECTIONS. Mixed carts allowed | One cart, one payment, two fulfilments, two tracking numbers |
| 11 | Design tool depth | Upload one image, choose front or back, drag to position and scale inside a print-area outline, live CSS-composited preview over the product photo. Price responds to print size | ~400 lines of vanilla JS, no dependencies, maps directly onto Qikink's placement SKU + width + height fields |
| 12 | Shipping | Flat ₹79, free above ₹999. Prepaid only. Staff enter carrier + AWB manually in the admin, which flips status to shipped and emails the customer | No courier API integration, no per-order API cost, no COD |
| 13 | Payments | Razorpay, already integrated with signature verification and a webhook dedup ledger | Kept rather than re-picked |
| 14 | Accounts | Browse, search, view products and build a cart entirely as a guest. Login or signup required **only** at "Proceed to checkout", with `?next=/checkout/` return | `Order.user` stays non-nullable: no schema change. Guest carts stay keyed on `session_key` and merge on login via the existing service |
| 15 | Admin | Hybrid: purpose-built Jinja2 pages for daily workflow, hardened Django admin underneath for long-tail CRUD | Two UIs, one design language |
| 16 | Delivery | Build everything, launch once | No phased public release; internal milestones still sequence the work |
| 17 | Design reference | `designs/IMG-20260703-WA00{16,17,20,21,22,23,24}.jpg`, home, collections, shop/search, cart, about, login, contact. Black/gold/cream premium menswear, INR | Loose visual and structural reference, not a spec to replicate |

---

## Part 2: Assumed decisions

Each was presented with alternatives and is taken as the recommended default. All are cheap to
change until the milestone that builds them begins.

### A: Platform and infrastructure

| ID | Decision | Chosen | Note |
|---|---|---|---|
| A1 | Image resizing | Generate 3 widths (400/800/1600) at upload into R2 | No per-transform billing, no dependency on a host feature |
| A2 | Sessions and cache | Database-backed sessions + database cache table | Redis would be a paid service for two low-traffic uses |
| A3 | Scheduled jobs | Qikink status poll · design-sanitise sweep · failed-job retry sweep · abandoned cart · low-stock alert · search-document reindex · coupon expiry · payment reconciliation · session and log prune · sitemap ping | All ten are cron-triggered endpoints with a manual run button |
| A4 | Email | Resend | Cleanest API, good deliverability, generous free tier |
| A5 | SMS / WhatsApp | None | Email only at launch |
| A6 | Error tracking | Sentry (`sentry-sdk[django]`, already a dependency) | Vercel keeps runtime logs 1 h on Hobby |
| A7 | Analytics | GA4 | Behind the cookie banner (L5) |
| A8 | Environments | Production + per-branch preview deployments on Neon branches | Preview gets its own database branch, seeded |
| A9 | Migrations | Manual `migrate` gate before promoting a deployment | Never auto-run in a build step; keeps rollbacks safe |
| A10 | Local dev | `vercel dev` + SQLite (`USE_SQLITE=1`) | Postgres-only features guarded; CI runs against Postgres |
| A11 | Repo layout | Flatten `backend/` to the repo root | Zero-config detection, default `STATIC_ROOT` behaviour |
| A12 | Python | 3.12 | Matches the existing `requires-python` |
| A13 | DRF surface | Internal JSON endpoints for the site's own JS, session + CSRF auth, not publicly documented | DRF earns its place for serializers, throttling and validation, not for a public API |
| A14 | Rate limiting | DRF throttles on the database cache | Vercel WAF stays available if abuse appears |
| A15 | Backups | Neon PITR + weekly `pg_dump` to R2, restore rehearsed once | A backup nobody has restored is not a backup |
| A16 | Domain | `civicforest.com` apex, `www` 301 → apex | Confirm the registrar and current DNS host before cutover |
| A17 | allauth | Install from PyPI pinned to `==65.19.1`; delete the vendored `django-allauth/` checkout | The checkout is untracked and would otherwise drift |

### B: Auth and accounts

| ID | Decision | Chosen | Note |
|---|---|---|---|
| B1 | Identifier | Email + password | Matches the existing custom `User` (no username, UUID pk) |
| B2 | Email verification | Mandatory, blocks checkout | Stops throwaway-address order fraud |
| B3 | Verification style | Emailed link | Code entry is available in allauth if preferred later |
| B4 | Social login | Google only | The login screenshot also shows Apple; Apple requires a paid developer account and a service ID, so it is deferred rather than dropped |
| B5 | Two-factor | Optional TOTP + 10 recovery codes, per user | Mandatory for staff (B10) |
| B6 | Trust this browser | On, 14 days | `MFA_TRUST_ENABLED`; avoids challenging 2FA users every login |
| B7 | Passkey login | Out | WebAuthn stays available in allauth if wanted later |
| B8 | Account deletion / data export | In-account request → admin action → anonymise and email confirmation | DPDP-aligned without an irreversible one-click delete |
| B9 | Remember me | 14 days | Staff sessions capped at 1 h separately |
| B10 | Staff access | Same login form, role-gated, **mandatory TOTP for staff**, obscure admin path from env, 1 h session | The current `StaffAdminMiddleware` DEBUG bypass is removed |
| B11 | Address book | Multiple addresses with one default | Existing `Address` model |
| B12 | Phone | Required at checkout, optional on the profile | Couriers need it |
| B13 | Login rate limits | allauth defaults | Tighten if abused |

### C: Catalogue and product data

| ID | Decision | Chosen | Note |
|---|---|---|---|
| C1 | Variant axes | Size × colour | Existing `ProductVariant` unique constraint |
| C2 | MRP + selling price | Both, with strike-through and computed percentage off | New `mrp` field; discount is never stored, always derived |
| C3 | Tax | Prices displayed **tax-inclusive**; per-product HSN code and rate stored; breakdown shown on the invoice | Adding tax at checkout is drip pricing under the CCPA guidelines. Rates configurable, not hardcoded, **confirm current apparel slabs with your CA** |
| C4 | Stock | Per-variant integer quantity | Existing field |
| C5 | Oversell guard | Re-validate at checkout, decrement on payment verified, inside a transaction with `select_for_update` | No reservation TTL to expire and leak |
| C6 | Backorder / pre-order | Out | |
| C7 | Collections | Dedicated `Collection` model, many-to-many with products | The old site rendered categories as collections; the screenshot shows curated collections with their own copy and imagery |
| C8 | Category depth | Two levels | `parent` FK already nullable |
| C9 | Badges | `New` auto from `created_at` window, `Sale` auto from the MRP gap, `Bestseller` manual | Matches the BESTSELLER / NEW / −15% badges in the shop screenshot |
| C10 | Product fields | description · fabric/material · care instructions · fit notes · model height and size worn · GSM · sleeve/neck type · size chart · **country of origin** · HSN code · tax rate · weight · dimensions | Country of origin is legally required, not optional |
| C11 | Size chart | Per-category table, admin-editable, in the product page's size-guide accordion | One chart maintained per garment type. E7 already lists size guide as an accordion, and a `<dialog>` cannot be opened without JavaScript, which P6 forbids relying on |
| C12 | Images | Product-level and variant-level, ordered, alt text required, max 8 per product, hover zoom + lightbox. No video | Colour swatch selection swaps the gallery |
| C13 | Related products | Same-category automatic, with a manual override list | Powers "You may also like" in the cart screenshot |
| C14 | Bundles / sets | Out | |
| C15 | Gift cards | Out | Adds a whole balance-and-liability subsystem |
| C16 | Product CSV | Import and export both | Bulk catalogue work without clicking |

### D: Shop, browse, search

| ID | Decision | Chosen | Note |
|---|---|---|---|
| D1 | Filters | category · size · colour · price range · material · availability · collection/badge | Exactly the facets in the shop screenshot |
| D2 | Filter mechanics | URL query parameters, server-rendered, **works with JavaScript disabled**; JS upgrades it to fetch-and-replace without a reload | Filter state is shareable and back-button correct |
| D3 | Facet counts | Shown beside every option, recomputed per filter state | The screenshot shows counts like "Hoodies (48)" |
| D4 | Sorts | relevance · newest · price ascending · price descending · popularity | Popularity from paid order-item counts |
| D5 | Pagination | Numbered, with prev/next | Matches the screenshot; better for SEO than infinite scroll |
| D6 | Page size | 12 | 4-across × 3 rows |
| D7 | Autocomplete | Overlay with product hits (thumbnail, name, price), matching categories, and popular queries | 250 ms debounce, keyboard navigable, `aria-live` count |
| D8 | Zero results | Spelling suggestion via trigram, plus popular products, plus the search term logged for the admin report | |
| D9 | Search logging | Keep `SearchQueryLog`; surface zero-result terms in the back-office | Shows demand for things not stocked |
| D10 | Recently viewed | Cookie-based strip of the last 6 products | No account needed |
| D11 | Quick view | Out | |
| D12 | Compare | Out | |
| D13 | Navigation | Simple nav, dropdown on SHOP only, plus the CUSTOMISE item | Six items; no mega menu at this catalogue size |
| D14 | Announcement bar | Admin-editable text, link and on/off toggle | Currently "FREE SHIPPING ON ALL ORDERS ABOVE ₹999" |

### E: Product page

| ID | Decision | Chosen |
|---|---|---|
| E1 | Gallery | Thumbnails plus main image, hover zoom on desktop, lightbox on click, swipe on mobile |
| E2 | Variant picker | Size buttons with out-of-stock struck through; colour swatches that swap the gallery |
| E3 | Delivery estimate | Pincode entry returns city, state and an SLA date range |
| E4 | Low-stock urgency | Shown **only when genuinely under the threshold**, never as a fixed message | 
| E5 | Add to cart | Slide-in drawer, matching the screenshots |
| E6 | Buy now | Out |
| E7 | Accordions | Description · fabric and care · shipping and returns · size guide |
| E8 | Trust strip | Kept: premium fabric, quality assured, fast delivery, easy returns |
| E9 | Share buttons | Out |
| E10 | Breadcrumbs | In, with `BreadcrumbList` markup |
| E11 | Sticky mobile buy bar | In, appears once the main buy panel scrolls out |

### F: Custom design line

| ID | Decision | Chosen | Note |
|---|---|---|---|
| F1 | Base blanks | Six: regular tee, oversized tee, hoodie, sweatshirt, polo, cap | Each mapped to a Qikink SKU per size and colour |
| F2 | Placements | Front and back | Priced separately; both may be used on one garment |
| F3 | Print method | Hidden: Qikink chooses | Exposing DTG vs embroidery invites choices customers cannot judge |
| F4 | Upload guidance | 300 DPI minimum · max 25 MB · PNG, JPEG or WebP · transparent-background advice · live print-area outline · a warning when the uploaded raster is too small for the chosen print size |
| F5 | Mockup preview | Live CSS composite over the product photograph | No server round-trip while dragging |
| F6 | Moderation | Admin approval queue before anything reaches Qikink | Protects against infringing or offensive artwork being printed under your brand |
| F7 | Pricing | Blank base price + print surcharge per placement, scaled by print area | Surcharges are admin-editable |
| F8 | Rights acknowledgement | Required checkbox, unticked, with the wording stored against the order | Evidence if a rights claim arrives |
| F9 | Design retention | Kept indefinitely so a customer can reorder; deletable on request | Listed at `/account/designs/` |
| F10 | Custom order status | Its own timeline: submitted → in production → dispatched → delivered, fed by Qikink polling |
| F11 | Qikink SKU mapping | An admin field per blank variant, validated against the sandbox before going live |
| F12 | Submit failure | Admin alert, exponential backoff retries, manual resubmit button, never silent |
| F13 | Custom returns policy | Defect-only within 7 days with an unboxing video; no change-of-mind or size swap | Mirrors Qikink's own terms, stated on the product page and in the returns policy |
| F14 | Sandbox toggle | `QIKINK_BASE_URL` switches host; sandbox requires `search_from_my_products: 0` |

### G: Cart

| ID | Decision | Chosen |
|---|---|---|
| G1 | Guest cart | Session-keyed, merged into the account cart on login (existing service and its edge-case tests) |
| G2 | Free-shipping progress bar | Kept, with the exact rupee shortfall as in the screenshot |
| G3 | Coupon entry | Both in the cart and at checkout |
| G4 | Line actions | Quantity stepper · remove · move to wishlist · clear cart |
| G5 | Abandoned cart email | One, four hours after the last change, to logged-in users only, with a one-click unsubscribe |
| G6 | Cart lifetime | 30 days, then swept |
| G7 | Max quantity per line | 10 |
| G8 | Cross-sell | "You may also like" row beneath the cart |
| G9 | Stock revalidation | On every cart view and again at checkout, with a clear message naming the affected line |

### H: Checkout and payments

| ID | Decision | Chosen | Note |
|---|---|---|---|
| H1 | Layout | Single page, collapsible sections, sticky order summary | Fewer steps, fewer drop-offs |
| H2 | Provider | Razorpay | Confirmed, #13 |
| H3 | Methods | UPI · cards · netbanking · wallets. No EMI, no BNPL | UPI is the majority of Indian digital payments |
| H4 | Checkout UX | Razorpay Standard Checkout modal | Customer never leaves the domain |
| H5 | Pincode | Auto-fills city and state, shows the delivery estimate | |
| H6 | Billing address | "Same as shipping" ticked by default, expandable | Ticking a *convenience* default is fine; the dark-pattern rule is about consent and charges |
| H7 | GSTIN for business buyers | Out | |
| H8 | Invoice | HTML invoice page, print-to-PDF, downloadable from order history, numbered sequentially per financial year | GST fields per `02-research.md` §5 |
| H9 | Terms checkbox | Required, unticked, before payment | |
| H10 | Failed payment | Retry from the order page for 24 h, then auto-cancel and release stock | |
| H11 | Coupon stacking | One coupon per order | |
| H12 | Order number | Keep `CF-XXXXXXXX`: random, non-sequential, unambiguous alphabet | Sequential numbers let customers enumerate other orders. Also stays inside Qikink's 15-character cap |
| H13 | Price-change guard | Cart is fully re-priced server-side at checkout; a changed price stops the flow with a visible diff | |
| H14 | Currency | INR only | |

### I: Post-purchase

| ID | Decision | Chosen | Note |
|---|---|---|---|
| I1 | Statuses | created · payment_pending · paid · processing · partially_shipped · shipped · delivered · cancelled · return_requested · returned · refunded · rto | `partially_shipped` and `rto` are new and necessary once orders split |
| I2 | Guest tracking | `/track/` by order number + email, rate-limited | "Track Order" is already in the footer |
| I3 | Customer cancellation | Allowed until the first shipment is marked shipped; releases stock and refunds automatically | Custom items cannot be cancelled once submitted to Qikink |
| I4 | Returns | Request form in the account with reason, comment and photos; admin queue | |
| I5 | Return window | 7 days from delivery | Matches "within 7 days" in the screenshots and Qikink's own claim window |
| I6 | Size exchange | Out: return and reorder instead | Qikink charges the seller for size swaps, and a stock exchange needs reverse logistics you do not have yet |
| I7 | Refund route | Razorpay refund to the original method | |
| I8 | Shipping fee on refund | Not refunded unless the item was defective | Stated in the policy |
| I9 | Reorder button | Out for stock items; **in** for saved custom designs | Reordering a design is the whole point of keeping it |
| I10 | Review request email | Three days after delivered, once, unsubscribable | |
| I11 | Invoice download | From order detail, any time | |

### J: Promotions

| ID | Decision | Chosen | Note |
|---|---|---|---|
| J1 | Coupon types | Percentage · flat amount · free shipping | No BOGO, no tiered |
| J2 | Coupon rules | min order · max total uses · **per-user limit** · start and end date · category or product scope · first-order-only · exclude sale items | The per-user limit is new and closes a real abuse hole |
| J3 | Automatic promotions without a code | Out | |
| J4 | Scheduled sale pricing | Per variant, with start and end datetimes | Drives the `Sale` badge and the strike-through |
| J5 | Newsletter + welcome code | In, **double opt-in**, checkbox unticked, one-click unsubscribe | The footer already promises 10% off the first order |
| J6 | Referrals | Out | |
| J7 | Loyalty points | Out | |
| J8 | Gift wrap or message | Out | |
| J9 | Dark-pattern guardrails | Every opt-in unticked · all-inclusive prices shown before commitment · no fabricated countdowns · decline wording neutral and equally prominent · one-click unsubscribe · cancellation no harder than signup | Not a nice-to-have: ₹10 lakh first-violation exposure |

### K: Reviews

| ID | Decision | Chosen | Note |
|---|---|---|---|
| K1 | Reviews and ratings | In, **verified purchasers only**: the review is tied to an `OrderItem` | No fake-review surface |
| K2 | Star average | On product cards, the product page, and in `AggregateRating` markup | |
| K3 | Photo uploads in reviews | Out at launch | Another moderation and storage surface |
| K4 | Moderation | Queue; nothing publishes unseen | |
| K5 | Fit feedback | In: runs small / true to size / runs large, aggregated on the product page | Cheap, and the single most useful datum for apparel returns |
| K6 | Helpful votes, sorting, seller replies | Out | |
| K7 | Product Q&A | Out | |

### L: Content, SEO, legal

| ID | Decision | Chosen | Note |
|---|---|---|---|
| L1 | Pages | About · Contact · FAQ · Shipping & Delivery · Returns & Exchanges · Size Guide · Track Order · Privacy Policy · Terms · **Grievance Redressal** · Sustainability · Our Story. Careers deferred | Grievance redressal is legally required |
| L2 | Page editing | Database-backed `Page` model, edited in the back-office | No redeploy to fix a policy typo |
| L3 | Blog | Out | |
| L4 | SEO | Per-page meta title and description · OG and Twitter cards · canonical URLs · JSON-LD (Product, Offer, AggregateRating, BreadcrumbList, Organization, WebSite) · `sitemap.xml` · `robots.txt` | |
| L5 | Cookie consent | Small banner, because GA4 sets cookies; analytics does not load until accepted | |
| L6 | Accessibility | WCAG 2.2 AA target, axe run in CI | |
| L7 | Language | English only | |
| L8 | Error and maintenance pages | Branded 404, 500 and maintenance-mode pages | |
| L9 | Compliance on the product page | Country of origin, tax-inclusive price, return window and delivery estimate all visible before add-to-cart | Consumer Protection (E-commerce) Rules 2020 |

### M: Notifications

| ID | Decision | Chosen |
|---|---|---|
| M1 | Customer emails | order confirmation · payment failed · shipped, one per shipment, with AWB · delivered · cancelled · refund processed · return received · return approved or rejected · custom design approved · custom design rejected · abandoned cart · review request · welcome · newsletter confirmation · allauth's verification, password reset, email change and 2FA notices |
| M2 | Email build | Branded HTML with a plaintext alternative, rendered from Jinja2, every send logged in `OutboundEmail` and resendable from the back-office |
| M3 | Staff alerts | new order · Qikink submission failure · low stock digest · payment amount mismatch · dead-lettered job · new contact message |
| M4 | Customer notification preferences | Out: transactional email is not optional, marketing has a one-click unsubscribe |
| M5 | Back-in-stock notifications | Out |
| M6 | Deliverability | SPF, DKIM and DMARC on the sending domain before launch; a bounced-email report in the back-office |

### N: Support

| ID | Decision | Chosen |
|---|---|---|
| N1 | Contact form | Saved to `ContactMessage` and emailed to support, with an optional order-number field as in the screenshot; honeypot plus rate limit, no CAPTCHA |
| N2 | Support inbox | In the back-office: list, mark handled, internal note |
| N3 | FAQ | Admin-editable question and answer entries, rendered as an accordion, with `FAQPage` markup |
| N4 | Live chat | Out |
| N5 | Contact details | Address, two emails, two phone numbers and store hours, as in the screenshot |

### O: Back-office

| ID | Decision | Chosen |
|---|---|---|
| O1 | Dashboard tiles | revenue today / 7 d / 30 d · orders by status · AOV · units sold · new customers · top products · low stock · pending design reviews · failed Qikink submissions · failed payments · abandoned carts · coupon usage · zero-result searches · conversion rate |
| O2 | Charts | Hand-rolled inline SVG sparkline and bar chart, no charting library |
| O3 | Order queue | filters by status, date, payment state and fulfilment kind · detail view · guarded status transitions · carrier and AWB entry per shipment · cancel · refund · resend any email · internal notes · packing slip · invoice · bulk status update · CSV export |
| O4 | Design review | full-resolution artwork · approve or reject with reason · manual Qikink resubmit · Qikink status and AWB · download the print-ready file |
| O5 | Product management | create, edit, archive · variant matrix bulk editor · drag-reorder images · bulk price and stock update · duplicate product · CSV import and export |
| O6 | Inventory | stock adjustments with a reason, recorded in `StockAdjustment` · per-variant low-stock threshold · stock-on-hand report |
| O7 | Coupons | CRUD · per-coupon usage report · retire |
| O8 | Customers | list and search · detail with orders and lifetime value · block · CSV export. No impersonation |
| O9 | Returns | queue · approve or reject · mark received · trigger refund |
| O10 | Content | static pages · announcement bar · homepage sections · FAQ entries · category and collection imagery |
| O11 | Roles | Owner (everything) · Manager (no staff or settings) · Fulfilment (orders, shipments, stock) · Support (orders read-only, returns, messages), Django groups with explicit permissions |
| O12 | Audit log | `django-auditlog` retained, viewable in the back-office |
| O13 | Reports | sales by day · by product · by category · GST summary by rate · coupon performance · inventory valuation · search terms with no results |
| O14 | Mobile | Order queue and shipment marking usable on a phone; the rest desktop-first |
| O15 | Visual style | The storefront's tokens, denser tables, no separate theme |

### P: Frontend craft

| ID | Decision | Chosen | Note |
|---|---|---|---|
| P1 | Visual direction | Keep the black / gold / cream premium look from the screenshots, tightened | Near-black `#0d0d0d`, gold `#c9a227`, cream `#f7f4ef` |
| P2 | Typography | A serif display face for headings and a humanist sans for body, **self-hosted as subset woff2** | No third-party font request on the critical path; licences recorded in the repo |
| P3 | CSS | `tokens.css` + `base.css` + one sheet per page area, native nesting and custom properties, no build step | Under 60 KB total uncompressed |
| P4 | JavaScript | Small ES modules per feature, loaded with `<script type="module">`, no bundler | Under 50 KB total |
| P5 | JS-driven interactions | cart drawer · search overlay · filters · gallery zoom · variant picker · accordions · mobile nav · size-chart modal · design tool · pincode check · toasts · quantity steppers |
| P6 | No-JS baseline | Browse, filter, sort, paginate, add to cart and check out **all work without JavaScript**, forms post normally and re-render | The design tool is the one exception and says so |
| P7 | Icons | One inline SVG sprite | |
| P8 | Images | `srcset` with three widths, `loading="lazy"` below the fold, WebP, explicit dimensions to prevent layout shift | WebP only, no AVIF and no JPEG fallback: WebP has been universal since 2020, so nine derivatives per image would triple storage and upload time for nothing. Never upscaled, so a narrow original is offered at fewer widths |
| P9 | Motion | Subtle, 150 ms, honours `prefers-reduced-motion` | |
| P10 | Dark mode toggle | Out | |
| P11 | Performance budget | LCP under 2.5 s on a throttled 4G profile, CLS under 0.1, under 50 KB JS and 60 KB CSS per page | Enforced by a check in CI |

### Q: Quality and operations

| ID | Decision | Chosen | Note |
|---|---|---|---|
| Q1 | Tests | Port the existing pytest suite (101 tests pass today), add view and template tests, target 80% coverage on service modules | Money paths get adversarial tests, not happy-path ones |
| Q2 | End-to-end | Playwright on three flows: signup and login, checkout with a genuinely HMAC-signed webhook, custom design upload | Keeps one Node dev dependency; it has already caught real bugs here |
| Q3 | CI | GitHub Actions: ruff → pytest on Postgres → `pip-audit` → Playwright → axe → CSS/JS size budget. Keep CodeQL and Dependabot | |
| Q4 | Template linting | `djlint` across both Jinja2 and DTL templates | |
| Q5 | Seed data | `seed_catalog` and `seed_dev_users` rewritten for the new schema; refuses to run when `DEBUG=False` | |
| Q6 | Maintenance mode | Environment flag serving a branded page, with staff bypass | |
| Q7 | Logging | JSON logs with a request id, no PII in log lines | Vercel keeps 1 h on Hobby, so Sentry carries history |
| Q8 | Uptime | External ping to `/healthz` every 5 minutes | |

---

## Part 3: Defaults applied where no answer was given

Two behaviours were about to be asked about and have been decided rather than left blank. Both are
one-line changes if you disagree.

| Item | Default taken | Alternative |
|---|---|---|
| The login wall at checkout | A **full login page** matching the screenshot, reached with `?next=/checkout/`, carrying a contextual line ("Sign in to complete your order") and the cart summary alongside so the customer can see what they are protecting | An inline login panel embedded as the first step of the checkout page |
| Wishlist for guests | The heart **prompts login**. No cookie-based guest wishlist | Store guest hearts in a cookie and merge them on login, as the cart does |

Everything in Part 2 marked as assumed follows the same rule: named, defaulted, reversible.

---

## Part 4: Non-goals

Deliberately excluded. Recorded so they are not silently reintroduced, and so the reason survives.

**Commerce features:** cash on delivery · guest checkout · size exchange · gift cards · bundles and
sets · pre-order and backorder · loyalty points · referrals · gift wrap and gift messages · multiple
currencies · international shipping · B2B pricing, quotes or purchase orders · GSTIN capture ·
marketplace or multi-vendor · subscriptions.

**Storefront features:** product video · quick view · product comparison · product Q&A · review photo
uploads · review helpful-votes and seller replies · back-in-stock notifications · live chat ·
blog · Hindi or any second language · dark-mode toggle · push notifications · social commerce feeds ·
Google Shopping or Meta catalogue sync.

**Technical:** React, Vue, Svelte or any frontend framework · Tailwind or any CSS framework · a
bundler, transpiler or CSS preprocessor · a second deployment target · Docker or Caddy in the
production path · Redis · Meilisearch, Typesense or Algolia · Celery and Vercel Queues (recorded as
the escape hatch in `02-research.md` §1, not built) · WebSockets · server-side rendering of a JSON API
for a separate client · a public documented REST API · GraphQL.

**Operational:** COD reconciliation · courier API integration · warehouse or ERP integration ·
multi-warehouse stock · returns pickup scheduling · automated fraud scoring · A/B testing framework ·
a CRM integration.

Anything on this list can be added later; none of it is architecturally blocked by the choices above.
The two that cost measurable revenue, guest checkout and COD, are called out again in
`02-research.md` §6 so the trade-off stays visible.


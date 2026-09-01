# 02: Verified research

Everything below was checked against primary sources on 2026-09-01, not recalled. Sources are listed
at the end of the file. Where a fact could not be confirmed it says so.

---

## 1. Vercel platform

### Django support

- Vercel detects a Django project by locating `manage.py`, executes it to discover
  `DJANGO_SETTINGS_MODULE`, then resolves the entrypoint from `WSGI_APPLICATION` or
  `ASGI_APPLICATION`. **If both are set, ASGI wins.** The current repo has both `config/wsgi.py` and
  `config/asgi.py`, so this must be made deliberate rather than incidental.
- Override the entrypoint with `[tool.vercel] entrypoint = "config.wsgi:application"` in
  `pyproject.toml`. A build hook goes in `[tool.vercel.scripts] build = "..."`.
- No `vercel.json` rewrites and no `/api` directory are required. Zero-config since April 2026.
- The whole Django project becomes **one** Vercel Function on Fluid compute, scaling with traffic.
- `collectstatic` runs **automatically** during the build; collected files are served by the Vercel
  CDN at `STATIC_URL`. Do not add a build script to call it.
- Supported static backends: `StaticFilesStorage`, `ManifestStaticFilesStorage`, WhiteNoise's
  `CompressedManifestStaticFilesStorage`. WhiteNoise is only active under `vercel dev` locally; in
  production the CDN serves the files.
- If `django-storages` is detected as the storage backend, Vercel runs `collectstatic` with the
  original settings so files upload straight to the provider during the build.
- `{% static %}` works in production and under `vercel dev`.
- Django Channels/WebSockets are supported on the same function; `InMemoryChannelLayer` only
  coordinates within one instance, so group broadcast needs an external channel layer. Not needed
  for this build.
- `vercel dev` requires CLI ≥ 50.38.0.

### Hard limits that change the design

| Limit | Value | Effect on this build |
|---|---|---|
| Request body | **4.5 MB** → `413 FUNCTION_PAYLOAD_TOO_LARGE` | Design artwork must go browser → R2 directly. Django never receives the bytes |
| Response body | **4.5 MB** → `500 FUNCTION_RESPONSE_PAYLOAD_TOO_LARGE` | CSV exports stream or are written to R2 and linked |
| Filesystem | Read-only except `/tmp` | No `MEDIA_ROOT`. `/tmp` only for transient Pillow work |
| Cron jobs | 100 per project on every plan | Not a constraint |
| Cron frequency | **Hobby: once per day, ±59 min slippage.** Pro/Enterprise: once per minute, per-minute precision | Qikink has no webhooks, so tracking freshness is gated here. Drives decision #3 |
| Function duration | Legacy non-Fluid: Hobby 60 s, Pro 300 s, Enterprise 900 s. Fluid raises this; Pro/Enterprise up to 1800 s in beta | CSV import and bulk jobs must chunk regardless |
| Bundle size | 500 MB standard, 5 GB with Large Functions (beta) | Pillow + psycopg + boto3 fit comfortably |
| Build step | 45 min max | Not a constraint |
| Proxied request | 120 s | Not a constraint |
| Env vars | 1000 per environment, 64 KB total | Not a constraint |
| Runtime logs | 1 h retention on Hobby, 1 day on Pro | Sentry is not optional if you want history |
| Git | Hobby cannot connect to repos owned by a Git **organisation** | Personal account or upgrade |

### Background work options that do exist

Rejected in favour of database job rows + cron (decision #7), but recorded because they are the
escape hatch if cron proves too coarse:

- **Celery runs on Vercel.** A `vercel://` broker backed by Vercel Queues is installed automatically
  when running on Vercel; `broker_url` defaults to `vercel://`. Workers are declared declaratively as
  `[[tool.vercel.subscribers]] entrypoint = "worker:app"`. There is no long-running daemon. Tasks
  execute as Vercel Functions. Results land in Runtime Cache by default, which the changelog itself
  describes as suitable only for "small data sizes and relatively short workflow runtimes".
  Concurrency caps, task duration ceilings and support for beat/chords are **not documented**: treat
  as unverified.
- **Vercel Queues** is a durable append-only log with consumer groups, retries, visibility timeouts,
  idempotency keys, delayed delivery, push and poll modes, and a **Python SDK** (`vercel-queue`).
  7-day message TTL.
- **Vercel Workflows** sits above Queues with durable steps and sleeps. Limits: 100,000 concurrency,
  50 MB max payload, 2 GB entity storage per run.

### Large uploads

Vercel's own guidance: functions "should be treated like a lightweight API layer, not a media
server." The sanctioned pattern is a token exchange: the server mints a short-lived upload token
after authenticating the user, the browser sends bytes straight to storage. Their security notes are
worth repeating verbatim in review: verify the user before returning a token, or "you're allowing
anonymous uploads", and narrow the allowed content types. The equivalent on R2 is a presigned
`PUT` with a content-type condition and a short expiry.

---

## 2. django-allauth

Version **65.19.1** (2026-08-13) is currently vendored, untracked, at `django-allauth/` in the
working tree. Facts read from that checkout's own documentation:

- **allauth ships Django Template Language templates and template tags** (`{% provider_login_url %}`,
  `{% load socialaccount %}`). Jinja2 cannot render them. Both engines must be configured: Jinja2 for
  site pages, DTL for allauth and Django admin. This is the single unavoidable consequence of
  choosing Jinja2 and is why the login/signup screens are built as DTL templates that share the same
  stylesheet.
- MFA supports TOTP, recovery codes and WebAuthn/passkeys. Passkeys are **disabled by default**.
- `MFA_RECOVERY_CODE_COUNT` 10, `MFA_RECOVERY_CODE_DIGITS` 8, `MFA_RECOVERY_CODES_SHOW_ONCE` False,
  `MFA_TOTP_PERIOD` 30 s, `MFA_TOTP_DIGITS` 6, `MFA_TOTP_TOLERANCE` 0 (raise to 1 if clock-drift
  complaints appear), `MFA_TOTP_ISSUER` should be set to `CivicForest` so it labels the QR code.
- `MFA_ALLOW_UNVERIFIED_EMAIL` defaults to **False**: a user cannot enable 2FA until their email is
  verified, and a 2FA user cannot add an unverified email. The rationale is an attacker signing up on
  someone's address and locking them out. Keep the default.
- `MFA_TRUST_ENABLED` (default False) adds a "Trust this browser?" choice with a signed cookie,
  `MFA_TRUST_COOKIE_AGE` 14 days, inheriting the session cookie's domain/secure/samesite settings.
- Email verification by 6-digit code exists as an alternative to links
  (`ACCOUNT_EMAIL_VERIFICATION_BY_CODE_ENABLED`) and is a prerequisite for passkey signup.
- 65.19.1 carries a security fix for an open redirector in the OpenID Connect RP-initiated logout
  endpoint: only relevant if `allauth.idp` is used, which it is not here. Pin at or above this
  version regardless.

---

## 3. Qikink

Qikink is operated by Huepress Fashion Pvt. Ltd., Coimbatore. 2,750+ SKUs across 350+ products:
t-shirts, hoodies, jackets, kidswear, headwear, bags, accessories, home and living, all-over print,
drinkware. Printing by DTG, DTF, sublimation, embroidery and vinyl. Branding add-ons: neck labels,
hang tags, poly bags, white-label packaging. No minimum order quantity, no subscription.

### API: confirmed

- Hosts: sandbox `https://sandbox.qikink.com`, live `https://api.qikink.com`.
- Token: `POST /api/token`, **form-encoded** (`application/x-www-form-urlencoded`, not JSON), fields
  `ClientId` and `client_secret`. Response field is `Accesstoken` (that exact capitalisation).
- The existing `apps/custom_orders/qikink.py` implements this correctly, including caching the token
  and pinning the request host as an SSRF guard. It is kept.
- Order payload, top level: `order_number`, `qikink_shipping`, `gateway` (`Prepaid` observed),
  `total_order_value`, `line_items[]`, `shipping_address`.
- `line_items[]`: `search_from_my_products`, `sku`, `quantity`, `price`. When
  `search_from_my_products` is `0`, **design code + mockup link + placement SKU are mandatory**.
- `shipping_address`: `first_name`, `last_name`, `address1`, `address2` (empty string allowed),
  `phone`, `email`, `city`, `zip`, `province`, `country_code`.
- **Type traps:** `quantity`, `price` and `total_order_value` must be sent as **strings**, while
  `search_from_my_products` must be a **number**. Mixed conventions in the same payload.
- **`order_number` is capped at 15 characters.** The existing `CF-XXXXXXXX` format is 11, which is safe, but
  the custom-line reference must not append a long suffix.
- **Sandbox and live have separate product databases.** `search_from_my_products: 1` against a
  product that exists only in the live dashboard fails with `Invalid SKU`. Sandbox work must use
  `0` with hand-supplied design fields.
- Observed errors: `Invalid SKU`; "Design code, Mockup Link and placement sku is mandatory";
  "Order no. cannot exceed 15 chars"; `401 Unauthorized` → regenerate the token and retry.
- **There is no outbound webhook.** Status and AWB are available only by polling. Qikink publishes no
  developer portal, no SDK and no public API reference. The credentials page and a Postman
  collection from their dashboard are the whole surface.
- Not documented anywhere public: rate limits, the full list of print type IDs, the full list of
  placement SKUs, COD-specific payload fields. These must be read off your own dashboard's Postman
  collection during M7 and recorded here.

### Fulfilment and returns: this dictates policy copy

- Dispatch within **48 hours**. Prepaid, COD and credits are all supported at their end.
- **Change of mind and wrong size are the seller's cost**. The fix is placing a new order at full
  price. There is no free size swap.
- Apparel measuring within **±0.5 inch** of spec is not a defect. Slight DTG colour deviation from the
  supplied artwork is expected behaviour, not a defect.
- Defect, misprint or damage claims: **within 7 days of delivery, with an unboxing video, photos of
  the item and photos of the original packaging.** Without the video "Qikink is not liable". Approved
  claims are refunded **to your Qikink credits**, not cash, in 2-3 days, or reprinted and reshipped.
- Later than 7 days incurs reprinting charges.
- RTO returns go to their Coimbatore facility; **a custom return address is not possible** because
  couriers do not offer it. Returned stock is inspected, added to your returns inventory, held **100
  days** and reusable; reshipping costs **₹20 + 18% GST per item** plus shipping. Discarded after 100
  days.
- If a pincode becomes unserviceable after the order was placed, **Qikink refunds nothing** and the
  seller absorbs the RTO.
- Lost shipments are refunded. No delivery attempt within 15 days (air) or 20 days (surface) lets you
  choose a reship or a refund.

---

## 4. Payments in India

- UPI carries **over 75% of digital transactions**; roughly 21 billion UPI transactions were processed
  in January 2026 alone. A checkout without UPI is not viable here.
- UPI itself has zero MDR, but prepaid-instrument wallets (Paytm, PhonePe, Amazon Pay balances) can
  attract a fee: worth knowing when reading settlement reports.
- The realistic provider set is Razorpay, Cashfree, PayU, PhonePe and Instamojo; all are RBI
  authorised and all cover UPI plus cards. Differences at this volume are small and mostly about
  support quality and settlement timing rather than headline rate.
- Razorpay is already integrated in `apps/payments` with HMAC signature verification, a
  `gateway_order_id` unique constraint, and a `WebhookEvent` table that deduplicates retried
  deliveries. The webhook secret is configured separately from the API secret.
- COD is roughly 40-60% of Indian apparel orders. It is deliberately **out of scope** (decision #12);
  the cost is RTO losses, fake orders, an order-confirmation step and cash reconciliation.

---

## 5. Indian regulatory requirements that are product features

### Consumer Protection (E-commerce) Rules, 2020

Mandatory on-site disclosures, each of which is a template or a model field, not paperwork:

- Total price with a **breakdown of every charge**. No charge may first appear at checkout.
- **Country of origin** per product. The government has issued 202 notices over incorrect
  country-of-origin declarations alone.
- Return, refund, exchange and warranty policy, plainly worded and easy to reach.
- Delivery timelines.
- Seller legal name, registered address and contact details.
- A **named grievance officer** with contact details and stated response timelines.

### CCPA Guidelines for Prevention and Regulation of Dark Patterns, 2023

Thirteen prohibited patterns under s.18 of the Consumer Protection Act, 2019. Confirmed enforcement
against seven of them, with direct consequences for this build:

| Pattern | What it forbids here |
|---|---|
| Basket sneaking | No pre-ticked newsletter, donation, insurance or add-on. "A pre-ticked default without a specific affirmative act is not consent" |
| Drip pricing | Shipping, handling and tax must be visible before commitment, not revealed at the last step |
| Confirm shaming | No "No, I'll pay full price" style decline wording |
| Forced action | No enrolment or marketing consent as a condition of purchase |
| Interface interference | Decline must be as visually prominent as accept |
| False urgency | **No recurring countdown timers and no "only 2 left" unless demonstrably true** |
| Subscription trap | Cancellation no harder than signup |

Enforcement context: a June 2025 advisory required platforms to self-audit within three months and
publish compliance self-declarations; 26 major platforms had filed by November 2025. Penalties run to
₹10 lakh for a first violation and ₹50 lakh for repeats; actual fines have been ₹1-7 lakh. Fixing the
interface later reduces exposure but does not erase liability. Zepto was told post-hoc changes could
not absolve past conduct.

### GST

- A tax invoice must carry the **HSN code**, description, quantity with unit code, taxable value, rate
  and tax amount, along with supplier and recipient details and place of supply.
- Apparel slabs have been revised more than once (the long-standing 5% under ₹1,000 / 12% above has
  changed, and some categories now break at ₹2,500). **Do not hardcode a rate**: store HSN and rate
  per product with a configurable default, and have your CA confirm the current numbers before launch.
- Selling through an e-commerce channel requires GST registration **regardless of the ₹40 lakh
  threshold**.
- B2C e-invoicing is **not** mandatory; e-invoicing applies to B2B above ₹5 crore turnover.
- GST is destination-based, so place of supply comes from the shipping state.

### DPDP Act, 2023

Explicit unticked consent for marketing (the existing `User.marketing_opt_in` models this), a privacy
notice stating purpose and retention, and a route for a data subject to export or delete their data.

---

## 6. Feature-breadth benchmark

Cross-checked against a current e-commerce feature audit and against Amazon, Myntra and Flipkart
behaviour. The recurring baseline, all of which is resolved in `01-decisions.md`:

**Finding products**: autocomplete tolerant of typos and partial words; category navigation shaped
around how shoppers think; breadcrumbs; sorting by price, popularity, newest, relevance; faceted
filters that stack, which the audit notes matters most past 500-1,000 SKUs.

**Product presentation**: multiple angles; full specifications; all sizes and colours under one
listing with per-variant price, imagery and live availability; reviews and ratings as the strongest
on-page trust signal; recommendation modules that work only when driven by real behaviour.

**Closing the sale**: a cart that persists across sessions; guest checkout, since forced account
creation is named a leading abandonment cause; multiple payment methods; shipping cost visible before
the final step; a low-friction single-page checkout; visible security signals; order tracking with
proactive messaging.

**Retention**: accounts with saved addresses and order history; social login to cut mobile friction;
wishlist as both convenience and a re-marketing signal; email capture with a welcome sequence and a
cart-abandonment message within the hour.

**Back office**: real-time inventory with low-stock alerts and automatic decrements; order volume,
AOV, top products and lifetime value reporting; editable SEO fields per product.

**Indian apparel norms specifically**: 7-30 day returns with the window shown on the product page and
in order details; size exchange treated as a first-class flow (deliberately deferred here, see I6);
size charts and "model wears" notes; pincode-based delivery estimates on the product page; COD
(deliberately out, see decision #12).

Two of these are knowingly declined and recorded as such: guest checkout (decision #14, login is
required at checkout) and COD. Both cost conversions; both were the owner's call.

---

## Sources

- [Deploy a Django app on Vercel](https://vercel.com/docs/frameworks/full-stack/django) · [Zero-configuration Django support](https://vercel.com/changelog/zero-configuration-django-support) · [Vercel limits](https://vercel.com/docs/limits) · [Cron jobs usage and pricing](https://vercel.com/docs/cron-jobs/usage-and-pricing) · [Bypassing the 4.5 MB body limit](https://vercel.com/guides/how-to-bypass-vercel-body-size-limit-serverless-functions) · [Vercel Queues](https://vercel.com/docs/queues) · [Run background tasks with Celery on Vercel](https://vercel.com/changelog/run-background-tasks-with-celery-on-vercel) · [Functions up to 30 minutes](https://vercel.com/changelog/vercel-functions-can-now-run-up-to-30-minutes)
- django-allauth 65.19.1: `ChangeLog.rst`, `docs/mfa/introduction.rst`, `docs/mfa/configuration.rst` from the checkout in this repo
- [Integrating Qikink into a custom store: issues log](https://dev.to/anupamswe/i-hit-these-issues-integrating-qikink-into-pinnaclewear-4ic9) · [Qikink returns and refunds](https://qikink.com/returns-and-refund/) · [Qikink platform summary](https://qikink.com/llms.txt) · [How Qikink works](https://qikink.com/how-qikink-works/)
- [Razorpay: payment gateway support for small businesses, 2026](https://razorpay.com/blog/payment-gateway-support-for-small-businesses/) · [UPI transaction charges and PPI fees](https://razorpay.com/learn/upi-transaction-charges/) · [Best payment gateways in India, 2026](https://statrys.com/blog/best-payment-gateways-in-india) · [Razorpay vs Cashfree vs PayU](https://surecart.com/blog/razorpay-vs-cashfree-vs-payu-wordpress-india/)
- [Consumer Protection (E-commerce) Rules, 2020](https://www.bwlegalworld.com/article/consumer-protection-e-commerce-rules-2020-a-blessing-for-consumers-305319) · [Country-of-origin enforcement notices](https://www.bwmarketingworld.com/article/govt-issues-202-notices-to-ecomm-cos-for-violating-country-of-origin-norm-410076) · [What India's dark pattern orders mean for digital business](https://www.barandbench.com/law-firms/view-point/from-nudge-to-notice-what-indias-dark-pattern-orders-mean-for-digital-business)
- [CBIC GST invoice rules](https://cbic-gst.gov.in/gst-invoice-rules.html) · [GST rates on clothing](https://cleartax.in/s/gst-rates-clothing) · [GST for e-commerce sellers](https://www.dmifinance.in/gst/gst-for-e-commerce-sellers-in-india/) · [B2C e-invoicing status](https://einvoice6.gst.gov.in/content/what-is-b2c-e-invoicing-e-invoicing-extended-to-b2c-transactions/)
- [30+ e-commerce website features you actually need in 2026](https://litextension.com/blog/ecommerce-website-features/) · [Must-have e-commerce features](https://www.bigcommerce.com/articles/ecommerce/features/) · [29 must-have features for e-commerce websites](https://www.searchenginejournal.com/ecommerce-guide/must-have-website-features/)


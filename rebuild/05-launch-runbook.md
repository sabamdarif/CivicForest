# Launch runbook (M10 operational steps)

The repo-side M10 work (CI gates, CSP, `check --deploy`, secret scan, tamper and replay tests,
`purge_demo`, `vercel.json`, the load-check script) is committed. This file is the ordered list of
steps that cannot be done from the repo: they flip live provider switches or touch shared
infrastructure. Nothing here runs automatically. Treat every live or destructive step as needing an
explicit go, and do the reversible rehearsals before the irreversible cutovers.

Run shell commands against production with `vercel env pull` for the real environment, or from a
local shell with the production variables exported. `manage.py` lines assume
`DJANGO_SETTINGS_MODULE=config.settings.production`.

## 0. Deploy-time, every production release

Release runs `migrate` before promoting (rollback is a redeploy, no DB rollback), so migrations
stay backward compatible.

1. `manage.py migrate`
2. `manage.py createcachetable` (first deploy only: the DB cache backend needs its table).
3. `manage.py bootstrap_roles` **(re-run required at the first post-M9 deploy).** Support and the
   returns queue depend on it: `bootstrap_roles` grants Support `content.change_contactmessage`
   (contact inbox) and `orders.view_returnrequest` / `orders.change_returnrequest` (returns queue),
   and those permissions did not exist when roles were first bootstrapped in M8, so that run skipped
   them. Re-running reconciles the groups and picks them up. Verify: a Support-group user can open
   the contact inbox and the returns queue in the back office.

Verify the release: `/healthz/` returns 200, and with `HEALTH_CHECK_TOKEN` the detailed body is green.

## M10.6 Restore rehearsal (reversible, do first)

Prove the backup path before anything depends on it.

1. `pg_dump` the production Neon database to a local file.
2. Create a scratch Neon branch and restore the dump into it (`psql <branch-url> < dump.sql`).
3. Point a local server at the branch (`DATABASE_URL=<branch-url>`), run the site, confirm pages and
   the admin load and an order reads correctly.
4. Delete the scratch branch. Record the dump size and restore time.

## M10.7 Qikink sandbox to live

Qikink has no public API reference: anything learned about the real payload or SKUs goes into
`rebuild/02-research.md` §3 immediately.

1. Set `QIKINK_BASE_URL` to the live host and `QIKINK_CLIENT_ID` / `QIKINK_CLIENT_SECRET` to live
   credentials. The path settings (`QIKINK_*_PATH`) are already env-driven if live differs.
2. Flip `search_from_my_products` to `1` only against live (sandbox cannot see live products).
3. Place one real low-value custom order end to end; confirm the print job is created and the design
   file is fetched (presigned GET). Order a physical test print of each blank and placement first:
   under Qikink's terms a mismatched reprint is your cost.

## M10.8 Razorpay to live (irreversible charge: confirm first)

1. Set `RAZORPAY_KEY_ID`, `RAZORPAY_KEY_SECRET`, `RAZORPAY_WEBHOOK_SECRET` to live values. Ensure
   `RAZORPAY_FAKE_MODE` is unset in production (it is read only by test and local settings).
2. Register the production webhook URL `/api/v1/payments/webhook/razorpay` in the Razorpay dashboard,
   subscribed to `payment.captured`, using the live webhook secret.
3. Place one real low-value order, confirm the webhook fulfils it (order PAID, `WebhookEvent` row,
   confirmation email), then refund it from order detail and confirm the refund.

## M10.9 Email authentication (SPF, DKIM, DMARC)

1. Add the Resend SPF and DKIM records to the sending domain's DNS; add a DMARC record
   (`p=quarantine` to start). `EMAIL_HOST`/`EMAIL_HOST_USER`/`RESEND_API_KEY` are already set.
2. Send one of each template (order confirmation, shipment, review request, newsletter opt-in,
   password reset) to a Gmail, an Outlook and a corporate mailbox; confirm inbox placement, not spam,
   and that SPF/DKIM/DMARC all pass in the headers.

## M10.10 Vercel Pro and real cron cadence

`vercel.json` ships daily crons because Hobby rejects a sub-daily schedule at build. On Pro, replace
the `crons` array with the real cadence below and redeploy, then confirm each fires (jobs panel /
`JobRun` rows, or the `x-vercel-cron-schedule` header in logs). `CRON_SECRET` must be set so Vercel
injects the bearer the endpoint checks.

```json
"crons": [
  { "path": "/internal/cron/sanitise_designs/",  "schedule": "*/5 * * * *" },
  { "path": "/internal/cron/reindex_search/",    "schedule": "*/30 * * * *" },
  { "path": "/internal/cron/poll_qikink/",       "schedule": "*/15 * * * *" },
  { "path": "/internal/cron/cart_reminders/",    "schedule": "17 * * * *" },
  { "path": "/internal/cron/cancel_stale_orders/","schedule": "25 * * * *" },
  { "path": "/internal/cron/review_requests/",   "schedule": "30 3 * * *" },
  { "path": "/internal/cron/expire_carts/",      "schedule": "30 21 * * *" }
]
```

Times are UTC: `30 3` is 09:00 IST, `30 21` is 03:00 IST.

## M10.11 Seed the real catalogue, remove demo data (destructive: confirm first)

1. Load the real catalogue (admin import or a one-off real seed, not `seed_catalog`).
2. `manage.py purge_demo --dry-run` to see what it would remove, then `manage.py purge_demo` and
   confirm at the prompt (or `--noinput` once the dry run looks right).
3. Verify no seeded product survives: no slug from `seed_catalog`'s `PRODUCTS` or `CUSTOM_BLANKS`
   remains, and the real products are intact.

## M10.12 DNS cutover

1. Point the apex at Vercel and set `www` to redirect to the apex (or the reverse, consistently).
2. Confirm the certificate issues, HSTS is served (production sets a one-year `max-age` with preload),
   and `DJANGO_ALLOWED_HOSTS` / `CSRF_TRUSTED_ORIGINS` include the live hostnames.

## M10.13 Post-launch watch (first week)

Check daily: Sentry for new issues, the back-office jobs panel for failed `JobRun` rows and stale
last-success times, and the failed-payment tile. The load check (`uv run python scripts/loadtest.py`,
M10.4) can be run against production during the first days to confirm p95 under 500 ms.

**Done when:** a real customer can buy a real product and a real custom print, both arrive, and every
email, invoice and tracking link along the way was correct.

# CivicForest Clothing

Premium menswear storefront for the Indian market: INR pricing, GST invoicing, prepaid
only. The committed code today is a Django 5.2 + DRF API with a separate Next.js
frontend, run locally through Docker Compose and Caddy. It is being rebuilt into a
single Django project that renders every page with Jinja2 and vanilla CSS/JS, deployed
as one Vercel function. The rebuild plan is `rebuild/`, and `rebuild/01-decisions.md`
is the decision register for it.

### Hard requirements

These are not preferences. A change that breaks one of them is wrong even if it works:

- **One deployment, no frontend framework.**
  Django renders every page with Jinja2. Vanilla CSS and vanilla ES modules only: no
  React, Vue, Tailwind, bundler, transpiler, CSS preprocessor or second host.

- **Money is computed server-side, always.**
  The client sends ids, quantities and a coupon code. It never sends a price, a discount
  or a total, and a total is never trusted from a client payload.

- **Uploads never pass through Django.**
  Vercel caps request bodies at 4.5 MB. Artwork goes from the browser straight to object
  storage with a short-lived presigned URL, and Django stores only the key.

- **Nothing reaches Qikink without a verified payment and a passed review.**
  Every submission carries an idempotency key, so a retry cannot create a second print job.

- **No dark patterns.**
  Consent boxes default to unticked, every charge is visible before the customer commits,
  and scarcity messages are derived from real stock. India's CCPA guidelines carry a
  ₹10 lakh first-violation penalty, so this is law, not taste.

- **Legally required product data is required.**
  Country of origin, HSN code and tax rate on every product, and a named grievance officer
  with contact details on the site. Details in `rebuild/02-research.md` section 5.

- **The site works without JavaScript.**
  Browse, filter, sort, paginate, add to cart and check out are forms that post and
  re-render. The custom design tool is the one documented exception.

- **Secrets stay server-side.**
  No key, token or credential in a template, a JS module, a log line or a client payload.

- **Agreed behaviour lives in `rebuild/01-decisions.md`.**
  Changing it means editing that file in the same commit, not only the code.

## How to Work Here

### Output style

No narration: don't explain what you're checking or why. No reasoning trace, no tool-call
list. Work silently: speak only for a blocking question or a finding the user genuinely
needs to know, in a 1-2 line status, e.g.
`M2 tasks 1-6 done, 7-11 (product page, JSON-LD, seed) remain.`

Never use an em dash, or `--` standing in for one, in a sentence anywhere: replies,
comments, commit messages, docs. A comma, a colon, parentheses or two sentences always say
it.

### Before implementing a feature

For anything past a small fix, switch to plan mode before writing code. Research how this
is typically solved, specifically the idiomatic way in Django, not the generic pattern that
shows up first. Once a candidate turns up, don't take it on faith: ask why it is the best
fit here, whether a better option exists, and what could go wrong given this project's
constraints (one function, read-only filesystem, no queue, no long-running process). Only
start implementing once it survives that scrutiny.

### Spec-driven workflow

One milestone at a time, no open-ended chat-driven changes:

1. `rebuild/04-build-plan.md` is the spec. Milestones M0 to M10, each with numbered tasks
   and acceptance criteria. Committed, and the source of truth for scope.
2. `progress.md` at the repo root is the working file: the current milestone, the approved
   plan for it in full, and a task checklist. Gitignored. Write it before the first line of
   code and keep it current as decisions change. A fresh session resumes from this file,
   never from what a previous conversation knew.
3. One commit per task or small group, naming the milestone and task number, e.g.
   `feat(catalog): add Collection model (M2.1)`.
4. Delete `progress.md` when the milestone is done.
5. Tick the task in `rebuild/04-build-plan.md` in the same commit.

Resuming: `git log --oneline -15` names the last milestone and task. If `progress.md`
exists a milestone is mid-flight, so read it and take the first unchecked task. If it does
not exist, the last milestone in the log is finished and the next one starts at step 2.

`plan.md`, `implementation_plan.md`, `tasks.md`, `remaining_plan.md` and `bug_fix_plan.md`
at the repo root describe the previous architecture and are superseded by `rebuild/`. M0
moves them to `rebuild/legacy/`. Do not treat them as current.

### YAGNI

Default to the laziest solution that actually works, and write nothing that is not needed.
This governs code, comments and commit messages alike.

Stop at the first rung that holds:

1. does this need to exist at all (skip speculative work);
2. does this repo already have a helper or pattern for it;
3. does Django or the stdlib do it;
4. can it be one line;
5. only then, the minimum new code.

Rung 2 matters here more than usual: the existing `apps/*/services.py` modules already hold
pricing, cart merge, order creation, upload sanitisation and the Qikink client. Read them
before writing a new one.

#### Third-party modules

Don't let that ladder tip into reinventing a wheel. Reach for a well-maintained third-party
module over hand-rolling or stretching the stdlib when either holds:

- the stdlib can technically do it, but not performantly enough for what this needs;
- doing it yourself would take enough work that you would effectively build your own
  version of the module.

Only pick a module that is actively maintained and reasonably current. An abandoned package
is worse than writing the code yourself, no matter how much it saves today. Check current
documentation (Context7 MCP, or the module's own docs) for its real API before writing
against it, rather than trusting memory. Anything added must also survive the platform:
it has to install into a Vercel Python function and work with a read-only filesystem and no
background process.

No unrequested abstractions: no interface for one implementation, no config option for a
value that never changes, no scaffolding for later. Write it when there is a reason to, not
because the shape of the file suggests it.

If it takes a paragraph to justify, do not do it. The length of the justification is the
signal: fix the code instead.

Never skimp on input validation at trust boundaries, error handling that prevents data loss,
security, or anything explicitly requested. Being lazy is about not adding, never about
dropping a check.

#### Comments

Before writing a comment, check it against all four:

- A comment exists to save the next contributor time, so keep it short and plain.
- Does the code already say this? Then don't write it.
- Am I describing a change I just made? That belongs in the commit, not here.
- Would a future reader get this wrong without a note? Only then write it.

One line, two at most, atop the function or class. Never inline. A comment that fails this
check gets deleted, not kept just in case.

Never cite a gitignored or ephemeral file from a comment, `progress.md` above all, because
it will not exist for the next reader. Cite only committed docs: `rebuild/`, the README.

#### Commit messages

Before writing a body, check it against all three:

- Does the subject line alone already say it? Then stop, no body.
- Am I about to list the diff bullet by bullet? Then stop, that is not a body.
- Am I recapping reasoning that already lives in a comment or this file? Then cut it.

Only write a body if the subject truly cannot carry the why. More than 2-3 sentences means
the commit is too big or the message is padded: split the commit, don't pad the message.

Commits follow [Conventional Commits](https://www.conventionalcommits.org):
`type(scope): subject`, e.g. `fix(payments): ...`, `feat(catalog): ...`, `test(cart): ...`.
Pick the type from what the commit does (`fix`, `feat`, `test`, `refactor`, `docs`, `chore`)
and the scope from the app or subsystem touched. A bare `scope: subject` with no type is not
acceptable.

No trailers. No `Signed-off-by`, no `Co-Authored-By`, no generated-by line. The subject, an
optional short body, nothing else.

#### Enforced, not just requested

Two rules above are checked by tooling, not left to compliance:

- **em dash**: `./check-before-commit.sh` greps the staged diff and fails on `—` in any added
  line, and on ` -- ` in added lines of `.md`, `.txt` and `.rst` only. `--` is left alone in
  code and CLI flags, where it is legitimate syntax, so prose is where this is caught.
- **commit body length**: `hooks/commit-msg` rejects a body over 5 lines, ignoring the
  subject, comments and trailer-shaped lines. Install it once per clone:
  `ln -sf ../../hooks/commit-msg .git/hooks/commit-msg`.

Comments cannot be enforced this cheaply, since a heuristic cannot tell a needed invariant
from clutter, so that one stays on the checklist above.

#### This file

Same rules apply here, and it is loaded into every request, so a line that does not change
what an agent does is pure cost. Record the invariant, not the bug that taught it: why one
commit did what it did belongs in that commit, and why a line is the way it is belongs on
the line. Hard ceiling of 1000 lines, and well under it is the goal.

### On long sessions

This file does not decay with turn count, and it does not come out of a compaction any
weaker than it went in. If anything you recall from earlier in this session conflicts with
what is written here, this file wins, not your summary of your own past behaviour. Before
writing a comment, a commit message, or picking a solution, re-check against the rule
itself, not against what you remember doing a few turns ago.

### Coding rules

- Modular, not fragmented. Code belongs in the app that owns the data, split as
  `models.py`, `services.py` (business logic), `serializers.py`, `views.py`, `urls.py`,
  `admin.py`. Logic goes in `services.py`, not in a view and not in a model method that
  reaches across apps. Don't create a new module or app when an existing one owns the
  concept, and don't scatter one feature across ten files to look modular.
- Be careful with unrequested destructive actions: deletions, force pushes, overwrites,
  migrations that drop columns.

- Keep comments in sync with the code they sit on. A stale comment is worse than none.
- When referencing anything in a comment or commit, make sure another contributor on their
  own machine can follow it: no local paths, no private links, no gitignored files.
- Every file opens with a short module docstring stating what it owns and any real
  invariant, at most a few lines. No SPDX line and no copyright line: this is a private
  single-owner codebase and a per-file licence header would be noise. If a file's docstring
  keeps growing, the excess belongs as a note at the lines it concerns.
- Fix a wrong or drifted docstring whenever you are in the file, including where your change
  did not touch what it got wrong. Reading enough of a file to change it is the only thing
  that catches drift, so repair it there.
- Tests: focused, not slop. Adversarial tests on money paths (tampered totals, replayed
  webhooks, coupon reuse, concurrent checkout of the last unit) earn their keep. Smoke tests
  that only confirm a deletion do not.
- Test code lives in `apps/<app>/tests/`, never mixed into the module it tests.
- Migrations stay backward compatible, because release runs `migrate` before promoting and
  rollback is a redeploy with no database rollback.
- Indentation follows `.editorconfig`: 4 spaces for Python, 2 for JS, JSON, CSS and YAML,
  tabs in Makefiles, LF endings, final newline, no trailing whitespace.

### Build, test, lint

Run everything before committing:

```bash
./check-before-commit.sh
```

That runs, in order: the em dash grep on the staged diff, `ruff check` and
`ruff format --check`, `makemigrations --check --dry-run` (fails if a model change has no
migration), and `pytest -q` (101 tests passing today). Everything runs with
`USE_SQLITE=1 DJANGO_SECRET_KEY=dev-key`, so no Postgres and no credentials are needed.

Single file or single test:

```bash
USE_SQLITE=1 DJANGO_SECRET_KEY=dev-key uv run pytest apps/cart/tests/test_cart.py
USE_SQLITE=1 DJANGO_SECRET_KEY=dev-key uv run pytest -k coupon -q
uv run ruff check apps/cart          # lint one app
uv run ruff format .                 # write formatting, not just check
```

Not covered by the script and worth running when relevant: `uv run pip-audit --strict`,
and `manage.py check --deploy` against `config.settings.production`. CI runs ruff, the
migration check, pytest against Postgres, pip-audit and CodeQL.

## What Is Already Documented

`README.md` is the user-facing reference: setup, environment variables, which API keys are
needed and where to get them, admin access, testing, deployment. Read it there instead of
re-deriving it, and update it in the same change when behaviour moves. It currently
documents the Docker and Next.js stack, so M0 rewrites it.

`rebuild/` holds what the README does not: `01-decisions.md` (every settled decision, with
IDs to cite), `02-research.md` (verified Vercel limits, allauth behaviour, the Qikink API and
its return terms, Indian compliance requirements, with sources), `03-architecture.md` (target
layout, data model, URL map, security controls), `04-build-plan.md` (the milestones).

Qikink publishes no public API reference. `rebuild/02-research.md` section 3 is the only
record of it, so anything learned about their real payload, print type IDs or placement SKUs
gets written there immediately.

Not in the README on purpose:

- `USE_SQLITE=1` forces the local SQLite file even when `DATABASE_URL` points elsewhere,
  which is what makes the offline test run work.
- `RAZORPAY_FAKE_MODE=True` lets tests sign their own webhooks with the local secret and
  reach the real fulfilment path without a Razorpay account. It is on in
  `config.settings.test` and must never be set in production.
- `HEALTH_CHECK_TOKEN` gates the detailed body of the health endpoint. `/healthz/` itself
  answers 200 to anyone, because an uptime monitor should not need a secret.

## Architecture

```
browser -> Caddy -> Next.js (frontend) and Django (backend)
Django: urls -> views/serializers -> services -> models -> Postgres
                              \-> Redis (cache, Celery broker), Meilisearch, S3/R2
```

Target after the rebuild, replacing the above:

```
browser -> Vercel (one Django function)
Django: urls -> views -> services -> models -> Neon Postgres
                    \-> Jinja2 templates, R2 (media), cron endpoints -> JobRun rows
```

Dependency direction is one way: views call services, services call models. A view that
contains business logic, or a model that calls another app's service, is the thing to fix.

### Apps

`backend/apps/`, each with `models.py`, `services.py`, `serializers.py`, `views.py`,
`urls.py`, `admin.py`, `tests/` where relevant. Open the file's docstring for detail; this
is only the index.

| App | Owns |
|---|---|
| `common` | `UUIDTimestampedModel` (UUID pk plus timestamps, inherited by nearly everything), pagination, throttles, error envelope, email helpers, middleware, test factories |
| `accounts` | `User` (email login, no username, UUID pk, `marketing_opt_in`), `Address`, profile endpoints |
| `catalog` | `Category`, `Product`, `ProductVariant` (size and colour, stock, price override, auto SKU), `ProductImage`, and the editable `Size`, `Color`, `Material`, `Tag` vocabularies |
| `cart` | `Cart` (one per user, or per session for guests), `CartItem`, `Coupon` with server-side validation, `Wishlist`. `services.price_cart` is the only place a total is computed |
| `orders` | `Order` and `OrderItem`, both fully snapshotted at creation so later catalogue edits cannot rewrite history. Random `CF-XXXXXXXX` public number |
| `payments` | `Payment` (one Razorpay order id per row), `WebhookEvent` (replay dedup ledger), signature verification |
| `custom_orders` | `CustomDesignOrder`, the Qikink client (`qikink.py`), and upload validation and re-encoding (`uploads.py`) |

`config/` holds `settings/{base,local,production,test}.py`, `urls.py`, `wsgi.py` and
`jinja2.py`. WSGI is the only entrypoint, deliberately: Vercel prefers ASGI when both
exist. `apps/search` is gone and M3 rebuilds it on Postgres full-text.

### Where to look first

| Symptom | Start here |
|---|---|
| Wrong price, discount or total | `apps/cart/services.py`, then `apps/orders/services.py` |
| Order stuck, wrong status | `apps/orders/services.py`, `apps/payments/views.py` (webhook) |
| Payment taken but no order | `apps/payments/views.py`, then `WebhookEvent` rows |
| Custom print not produced | `apps/custom_orders/services.py`, then `qikink.py`, then the order's review status |
| Upload rejected or corrupt | `apps/custom_orders/uploads.py` |
| Stock wrong after a sale | the fulfilment transaction in `apps/orders/services.py` |
| Cart lost or duplicated on login | `apps/cart/services.py`, `merge_guest_cart_into_user` |
| Admin returns 404 | `DJANGO_ADMIN_URL` is unset, so the admin sits on an unreachable path, or the staff user has no confirmed TOTP |

### Common tasks

**Adding a field to a catalogue model**

1. `apps/catalog/models.py`, with a docstring note only if the field carries a non-obvious
   invariant.
2. `uv run python manage.py makemigrations catalog` (the check in
   `check-before-commit.sh` fails the commit if this is skipped).
3. Expose it in `apps/catalog/serializers.py` explicitly. Never `fields = "__all__"`, and
   price and stock stay read-only in output.
4. Add it to `apps/catalog/admin.py` so staff can set it.
5. Update `management/commands/seed_catalog.py` if the field is required.
6. Test in `apps/catalog/tests/`.

**Adding an internal JSON endpoint**

1. Logic goes in the app's `services.py`, not the view.
2. Serializer with explicit fields, validating everything that came from the client.
3. View with an explicit permission class and a throttle scope. Querysets scoped to
   `request.user` for anything user-owned, so an id from a payload cannot reach another
   user's row.
4. Route in the app's `urls.py`, included from `config/urls.py`.
5. Test the unhappy paths: unauthenticated, another user's object, tampered amounts.


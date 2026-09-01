# CivicForest: Full Rebuild Plan

Rebuild of the CivicForest Clothing storefront onto **Django + DRF + Jinja2 + vanilla CSS and
vanilla JS, deployed as a single Vercel project.** Written 2026-09-01.

## Read in this order

| File | Contents |
|---|---|
| [`01-decisions.md`](./01-decisions.md) | Every decision that shapes the build. 17 confirmed by the owner; the rest taken as recommended defaults and flagged for veto. **Start here.** |
| [`02-research.md`](./02-research.md) | The verified platform, vendor and legal facts the decisions rest on: Vercel limits, django-allauth behaviour, the Qikink API and its return policy, Indian e-commerce compliance. Cited. |
| [`03-architecture.md`](./03-architecture.md) | Target architecture: repo layout, settings, dual template engines, URL map, data model, every integration, the frontend system, the admin, security, deployment. |
| [`04-build-plan.md`](./04-build-plan.md) | Ordered milestones with file-level tasks and acceptance criteria, risk register, launch checklist. |

## What this supersedes

`plan.md`, `implementation_plan.md`, `tasks.md`, `remaining_plan.md` and `bug_fix_plan.md` at the
repo root describe the **previous** architecture: Next.js App Router frontend, Docker Compose,
Caddy, Redis, Celery, Meilisearch, split frontend/backend hosting. They are kept for history.
Where they disagree with these four documents, **these win.**

## One-paragraph summary

One Django project serves every page as a server-rendered Jinja2 template, styled with hand-written
CSS and enhanced with small vanilla ES modules: no framework, no bundler, no second deployment.
django-allauth handles email/password login, optional TOTP two-factor and Google OAuth. The
catalogue is stock-fulfilled and shipped by CivicForest; a separate **CUSTOMISE** line lets a
customer upload artwork onto a blank garment, which Qikink prints and dropships. A cart may hold
both kinds of item: one payment through Razorpay, two fulfilments, two tracking numbers. Staff run
the store from purpose-built Jinja2 back-office pages, with a hardened Django admin underneath for
long-tail CRUD. Postgres lives on Neon, files on Cloudflare R2, deferred work runs as
database-backed job rows swept by cron-triggered endpoints.

## Status

Planning complete. No implementation has started. No existing application code has been modified.

## How to change a decision

Every decision in `01-decisions.md` carries an ID (`A4`, `K3`, `O11`…). To override one, name the ID
and the option letter: e.g. `B4b` to add Apple sign-in, `K3b` to allow photo uploads in reviews.
Anything marked **assumed** in that document has not been explicitly confirmed and can be changed at
no cost until the milestone that builds it starts.

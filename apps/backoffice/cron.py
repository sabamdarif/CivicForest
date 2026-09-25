"""Cron job registry and the bearer-gated `/internal/cron/<name>/` endpoints (M8.13).

A run ledger, not the `03-architecture.md` §7 engine: each job is a service function that runs a
bounded batch and returns how many items it processed, and `run_named_job` wraps one run in a
`JobRun` row (running to done/failed). The same runner backs the back-office "run now" button,
which is staff-gated instead of bearer-gated, so the secret never reaches a browser.

Idempotency already lives in the commands (`idempotency_key`, `WebhookEvent`, `CouponRedemption`),
and nothing enqueues rows, so no handler registry, per-key dedup, backoff or dead-letter is built.
"""

from __future__ import annotations

import secrets

from django.conf import settings
from django.http import HttpResponse, JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from apps.cart import services as cart_services
from apps.common.models import JobRun
from apps.custom_orders import services as custom_services
from apps.orders import services as order_services
from apps.search import services as search_services

# name -> a callable running one bounded batch and returning items_processed. cart_reminders only
# counts the backlog: the send waits for M9's signed-token unsubscribe, per the command's own note.
CRON_JOBS = {
    "expire_carts": lambda: cart_services.expire_dormant(500),
    "cart_reminders": lambda: cart_services.carts_awaiting_reminder()[:500].count(),
    "cancel_stale_orders": lambda: order_services.cancel_stale_pending_orders(500),
    "sanitise_designs": lambda: custom_services.sanitise_pending(50),
    "poll_qikink": custom_services.poll_open_orders,
    "reindex_search": lambda: search_services.reindex(stale=True, batch=500),
}


def run_named_job(name: str) -> JobRun | None:
    """Run one registered job inside a JobRun row. Returns the row, or None for an unknown name.
    A job that raises is recorded as failed with its error, never propagated."""
    job = CRON_JOBS.get(name)
    if job is None:
        return None
    run = JobRun.objects.create(name=name)
    try:
        processed = job()
    except Exception as exc:  # noqa: BLE001
        JobRun.objects.filter(pk=run.pk).update(
            status=JobRun.Status.FAILED, last_error=str(exc), finished_at=timezone.now()
        )
    else:
        JobRun.objects.filter(pk=run.pk).update(
            status=JobRun.Status.DONE,
            items_processed=processed or 0,
            finished_at=timezone.now(),
        )
    run.refresh_from_db()
    return run


def _authorized(request) -> bool:
    expected = settings.CRON_SECRET
    supplied = request.headers.get("Authorization", "").removeprefix("Bearer ").strip()
    return bool(expected) and secrets.compare_digest(supplied, expected)


@csrf_exempt
@require_POST
def run_job(request, name):
    """The external scheduler's entry point: `POST /internal/cron/<name>/` with a Bearer token."""
    if not _authorized(request):
        return HttpResponse(status=401)
    run = run_named_job(name)
    if run is None:
        return JsonResponse({"error": "unknown job"}, status=404)
    ok = run.status == JobRun.Status.DONE
    return JsonResponse(
        {
            "job": name,
            "status": run.status,
            "items_processed": run.items_processed,
            "last_error": run.last_error,
        },
        status=200 if ok else 500,
    )

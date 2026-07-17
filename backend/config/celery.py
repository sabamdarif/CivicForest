import os

from celery import Celery
from celery.schedules import crontab
from celery.signals import before_task_publish, task_prerun

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local")

app = Celery("civicforest")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()


# Thread the request/correlation ID from the web process into the worker so one failed
# checkout traces web → task in the logs (plan.md §16). Stamped as a message header on
# publish, restored onto the worker's contextvar before the task runs.
@before_task_publish.connect
def _stamp_request_id(headers=None, **_):
    from apps.common.middleware import get_request_id

    if headers is not None:
        headers["request_id"] = get_request_id()


@task_prerun.connect
def _restore_request_id(task=None, **_):
    from apps.common.middleware import set_request_id

    rid = getattr(task.request, "request_id", None) if task else None
    set_request_id(rid or "-")


# Periodic jobs. Qikink has no outbound webhook, so we pull custom-order status on a
# schedule; the nightly reindex is the search-sync safety net (plan.md §7, §8).
app.conf.beat_schedule = {
    "poll-custom-order-statuses": {
        "task": "apps.custom_orders.tasks.poll_custom_order_statuses",
        "schedule": crontab(minute="*/20"),
    },
    "nightly-search-reindex": {
        "task": "apps.search.tasks.reindex_all",
        "schedule": crontab(hour=3, minute=17),
    },
}

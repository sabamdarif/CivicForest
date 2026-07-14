import os

from celery import Celery
from celery.schedules import crontab

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local")

app = Celery("civicforest")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()

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

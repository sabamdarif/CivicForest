"""Reports (M8.14, O13): the view gate, the hub, and the streamed CSV export.

Reports are read-only, gated by ``view_order``. Each report exports through the shared streamed
CSV helper, so the export is a StreamingHttpResponse whose first line is the header.
"""

import pytest
from django.contrib.auth.models import Permission
from django.http import StreamingHttpResponse
from django.urls import reverse

from apps.common.factories import StaffUserFactory, login_staff_with_mfa
from apps.search.models import SearchQueryLog

pytestmark = pytest.mark.django_db


def _staff_with(client, *codenames):
    user = StaffUserFactory()
    for codename in codenames:
        user.user_permissions.add(Permission.objects.get(codename=codename))
    login_staff_with_mfa(client, user=user)
    return user


def test_reports_requires_permission(client):
    _staff_with(client)
    assert client.get(reverse("backoffice:reports")).status_code == 404


def test_hub_renders(client):
    _staff_with(client, "view_order")
    assert client.get(reverse("backoffice:reports")).status_code == 200


def test_sales_by_day_export_streams_header(client):
    _staff_with(client, "view_order")

    response = client.get(
        reverse("backoffice:reports"), {"report": "sales_by_day", "export": "csv"}
    )

    assert isinstance(response, StreamingHttpResponse)
    assert next(iter(response.streaming_content)).decode().startswith("Day,Orders,Revenue")


def test_zero_result_term_appears_in_hub(client):
    SearchQueryLog.objects.create(query="nonesuchproduct", result_count=0)
    _staff_with(client, "view_order")

    body = client.get(reverse("backoffice:reports")).content.decode()

    assert "nonesuchproduct" in body


def test_unknown_report_export_falls_back_to_hub(client):
    _staff_with(client, "view_order")

    response = client.get(reverse("backoffice:reports"), {"report": "bogus", "export": "csv"})

    assert response.status_code == 200  # renders the hub, does not stream

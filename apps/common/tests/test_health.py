import pytest
from django.test import Client, override_settings


def test_healthz_is_public_and_reveals_nothing():
    response = Client().get("/healthz/")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.django_db
@override_settings(HEALTH_CHECK_TOKEN="probe-secret")
def test_healthz_reports_dependencies_for_the_token_holder():
    response = Client().get("/healthz/", headers={"X-Health-Token": "probe-secret"})

    assert response.status_code == 200
    assert response.json()["checks"] == {"database": "ok", "cache": "ok"}


@override_settings(HEALTH_CHECK_TOKEN="probe-secret")
def test_healthz_withholds_detail_from_a_wrong_token():
    response = Client().get("/healthz/", headers={"X-Health-Token": "wrong"})

    assert response.status_code == 200
    assert "checks" not in response.json()

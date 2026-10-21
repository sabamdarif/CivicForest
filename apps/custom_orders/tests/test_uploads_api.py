"""The R2 direct-upload path (M7.2, M7.3).

Django never receives image bytes: the client gets a presigned URL, PUTs to storage (the
local dev receiver here), then confirms to trigger sanitisation. These tests cover the trust
boundary (auth, declared size) and the sanitise outcome (clean re-encode vs a disguised
non-image)."""

import pytest
from rest_framework.test import APIClient

from apps.custom_orders.models import DesignUpload

from .conftest import make_png_bytes

pytestmark = pytest.mark.django_db


def _client(user=None):
    client = APIClient()
    if user is not None:
        client.force_authenticate(user)
    return client


def _upload(client, content_type, body, declared_bytes=None):
    """Full round trip: mint URL, PUT bytes to the dev receiver, confirm to sanitise."""
    resp = client.post(
        "/api/v1/designs/upload-url/",
        {"content_type": content_type, "bytes": declared_bytes or len(body)},
        format="json",
    )
    assert resp.status_code == 201, resp.data
    design_id = resp.data["design_id"]
    put = client.put(resp.data["upload_url"], data=body, content_type=content_type)
    assert put.status_code == 200
    done = client.post(f"/api/v1/designs/{design_id}/complete/")
    assert done.status_code == 200
    return DesignUpload.objects.get(id=design_id)


def test_upload_url_requires_authentication():
    resp = _client().post(
        "/api/v1/designs/upload-url/",
        {"content_type": "image/png", "bytes": 1000},
        format="json",
    )
    assert resp.status_code in (401, 403)


def test_upload_url_rejects_oversized_declared_size(user, settings):
    settings.DESIGN_UPLOAD_MAX_BYTES = 1024
    resp = _client(user).post(
        "/api/v1/designs/upload-url/",
        {"content_type": "image/png", "bytes": 5_000_000},
        format="json",
    )
    assert resp.status_code == 400


def test_upload_url_rejects_unsupported_content_type(user):
    resp = _client(user).post(
        "/api/v1/designs/upload-url/",
        {"content_type": "application/pdf", "bytes": 1000},
        format="json",
    )
    assert resp.status_code == 400


def test_bytes_never_reach_django_on_upload_url(user):
    """The mint step only records intent and returns a URL: no image is stored yet."""
    resp = _client(user).post(
        "/api/v1/designs/upload-url/",
        {"content_type": "image/png", "bytes": 4096},
        format="json",
    )
    design = DesignUpload.objects.get(id=resp.data["design_id"])
    assert design.status == DesignUpload.Status.UPLOADING
    assert design.r2_key_print == ""


def test_happy_path_sanitises_to_print_ready_png(user):
    design = _upload(_client(user), "image/png", make_png_bytes(size=(2000, 2000)))
    assert design.status == DesignUpload.Status.READY
    assert design.mime == "image/png"
    assert design.width_px == 2000 and design.height_px == 2000
    assert design.r2_key_print and design.r2_key_raw == ""
    assert design.review_status == DesignUpload.ReviewStatus.AUTO_OK


def test_low_resolution_raster_is_flagged(user):
    design = _upload(_client(user), "image/png", make_png_bytes(size=(64, 64)))
    assert design.status == DesignUpload.Status.READY
    assert design.review_status == DesignUpload.ReviewStatus.FLAGGED


def test_disguised_non_image_is_rejected(user):
    design = _upload(_client(user), "image/png", b"this is not an image at all")
    assert design.status == DesignUpload.Status.FAILED
    assert design.review_status == DesignUpload.ReviewStatus.REJECTED
    assert design.r2_key_print == ""

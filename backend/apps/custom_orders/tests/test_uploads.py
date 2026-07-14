import io

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from PIL import Image

from apps.custom_orders.uploads import UploadError, validate_and_reencode

from .conftest import make_png_bytes

pytestmark = pytest.mark.django_db


def test_valid_png_is_accepted_and_reencoded():
    f = SimpleUploadedFile("art.png", make_png_bytes(), content_type="image/png")
    result = validate_and_reencode(f)
    assert result.name == "design.png"
    # Output is a real PNG.
    img = Image.open(io.BytesIO(result.read()))
    assert img.format == "PNG"


def test_renamed_executable_is_rejected_by_content_sniff():
    # A script masquerading as a .png — the extension lies, the bytes don't.
    payload = b"#!/bin/sh\nrm -rf /\n" + b"A" * 100
    f = SimpleUploadedFile("art.png", payload, content_type="image/png")
    with pytest.raises(UploadError) as exc:
        validate_and_reencode(f)
    assert exc.value.code == "unsupported_type"


def test_exif_is_stripped_on_reencode():
    jpeg_with_exif = make_png_bytes(with_exif=True)
    # Sanity: the source really does carry EXIF.
    assert Image.open(io.BytesIO(jpeg_with_exif)).getexif().get(0x010F) == "SecretCameraMaker"

    f = SimpleUploadedFile("photo.jpg", jpeg_with_exif, content_type="image/jpeg")
    result = validate_and_reencode(f)
    out = Image.open(io.BytesIO(result.read()))
    assert out.getexif().get(0x010F) is None  # EXIF gone after re-encode


@override_settings(DESIGN_UPLOAD_MAX_BYTES=500)
def test_oversized_file_is_rejected():
    f = SimpleUploadedFile("big.png", make_png_bytes(size=(256, 256)), content_type="image/png")
    with pytest.raises(UploadError) as exc:
        validate_and_reencode(f)
    assert exc.value.code == "file_too_large"


@override_settings(DESIGN_UPLOAD_MAX_DIMENSION=32)
def test_over_dimension_image_is_rejected():
    f = SimpleUploadedFile("wide.png", make_png_bytes(size=(64, 64)), content_type="image/png")
    with pytest.raises(UploadError) as exc:
        validate_and_reencode(f)
    assert exc.value.code == "dimensions_too_large"


def test_empty_file_is_rejected():
    f = SimpleUploadedFile("empty.png", b"", content_type="image/png")
    with pytest.raises(UploadError) as exc:
        validate_and_reencode(f)
    assert exc.value.code == "empty_file"

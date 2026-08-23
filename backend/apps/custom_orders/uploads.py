"""Design-upload validation & sanitisation.

Client-side checks are cosmetic (preview only) and never trusted. Here we:
  1. cap the byte size,
  2. **content-sniff** the real MIME (not the extension) with ``filetype``,
  3. open + verify with Pillow and cap dimensions,
  4. **re-encode** through Pillow to a clean PNG — this strips EXIF/metadata and
     neutralises any payload embedded in the original container.

The re-encoded bytes are what we store and later hand to Qikink (plan.md §8, §12)."""

from __future__ import annotations

import io

import filetype
from django.conf import settings
from django.core.files.base import ContentFile
from PIL import Image, UnidentifiedImageError

ALLOWED_MIME = {"image/png", "image/jpeg", "image/webp"}


class UploadError(Exception):
    def __init__(self, message: str, code: str = "invalid_upload"):
        super().__init__(message)
        self.message = message
        self.code = code


def _inspect(uploaded_file, max_bytes: int, max_dim: int) -> tuple[bytes, Image.Image]:
    """Shared gate for every image that enters the system: size cap, content-sniff,
    Pillow verify, dimension cap. Returns the raw bytes and an opened image."""
    raw = uploaded_file.read()
    if len(raw) == 0:
        raise UploadError("The uploaded file is empty.", code="empty_file")
    if len(raw) > max_bytes:
        raise UploadError(
            f"File is too large (max {max_bytes // (1024 * 1024)} MB).", code="file_too_large"
        )

    # Content-sniff: trust the bytes, not the extension the client claimed.
    kind = filetype.guess(raw)
    if kind is None or kind.mime not in ALLOWED_MIME:
        raise UploadError("Only PNG, JPEG, or WebP images are accepted.", code="unsupported_type")

    try:
        image = Image.open(io.BytesIO(raw))
        image.verify()  # detects truncated/corrupt payloads
        image = Image.open(io.BytesIO(raw))  # re-open: verify() leaves the file unusable
    except (UnidentifiedImageError, OSError) as exc:
        raise UploadError("That file isn't a readable image.", code="unreadable_image") from exc

    if image.width > max_dim or image.height > max_dim:
        raise UploadError(
            f"Image is too large ({image.width}×{image.height}); max {max_dim}px per side.",
            code="dimensions_too_large",
        )
    return raw, image


def validate_and_reencode(uploaded_file) -> ContentFile:
    """Return a sanitised PNG ``ContentFile`` or raise ``UploadError``.

    The returned file is safe to store: it is a freshly-encoded raster with no original
    container metadata carried over."""
    _, image = _inspect(
        uploaded_file,
        getattr(settings, "DESIGN_UPLOAD_MAX_BYTES", 15 * 1024 * 1024),
        getattr(settings, "DESIGN_UPLOAD_MAX_DIMENSION", 8000),
    )

    # Re-encode to a clean PNG — this is the sanitisation step (drops EXIF/ICC/payloads).
    out = io.BytesIO()
    image.convert("RGBA").save(out, format="PNG")
    out.seek(0)
    return ContentFile(out.read(), name="design.png")


def validate_product_image(uploaded_file) -> None:
    """Run the same checks on an admin-uploaded product photo, but keep the original
    encoding — re-encoding studio JPEGs to PNG would multiply their served size."""
    _inspect(
        uploaded_file,
        getattr(settings, "PRODUCT_IMAGE_MAX_BYTES", 15 * 1024 * 1024),
        getattr(settings, "DESIGN_UPLOAD_MAX_DIMENSION", 8000),
    )
    uploaded_file.seek(0)


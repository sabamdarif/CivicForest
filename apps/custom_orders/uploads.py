"""Design-upload validation & sanitisation.

Client-side checks are cosmetic (preview only) and never trusted. The real gate runs here,
out of the request path (M7.3): the raw upload lands in private R2 straight from the browser,
and this module fetches it, then

  1. caps the byte size,
  2. **content-sniffs** the real MIME (not the extension) with ``filetype``,
  3. opens + verifies with Pillow and caps dimensions,
  4. **re-encodes** through Pillow to a clean PNG, stripping EXIF/ICC and neutralising any
     payload embedded in the original container.

The re-encoded PNG is written back to R2 as the print-ready file, the raw upload is deleted,
and only the clean raster is retained and later handed to Qikink (rebuild/03-architecture.md
§8, §12)."""

from __future__ import annotations

import io

import filetype
from django.conf import settings
from django.core.files.base import ContentFile
from django.utils import timezone
from PIL import Image, UnidentifiedImageError

from apps.common import r2

ALLOWED_MIME = {"image/png", "image/jpeg", "image/webp"}

# The longest print edge a blank offers, used only to turn pixel dimensions into a coarse
# "is this raster big enough at all" DPI. The design tool computes the precise DPI live
# against the actual placement; this stored figure just drives the moderation flag.
NOMINAL_PRINT_INCHES = 12
MIN_PRINT_DPI = 100


class UploadError(Exception):
    def __init__(self, message: str, code: str = "invalid_upload"):
        super().__init__(message)
        self.message = message
        self.code = code


def _inspect_bytes(raw: bytes, max_bytes: int, max_dim: int) -> tuple[bytes, Image.Image]:
    """Shared gate for every image that enters the system: size cap, content-sniff, Pillow
    verify, dimension cap. Returns the raw bytes and an opened image."""
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


def _inspect(uploaded_file, max_bytes: int, max_dim: int) -> tuple[bytes, Image.Image]:
    return _inspect_bytes(uploaded_file.read(), max_bytes, max_dim)


def _reencode_png(image: Image.Image) -> bytes:
    """Re-encode to a clean PNG. This is the sanitisation step: it drops EXIF/ICC and any
    payload smuggled into the original container."""
    out = io.BytesIO()
    image.convert("RGBA").save(out, format="PNG")
    return out.getvalue()


def validate_and_reencode(uploaded_file) -> ContentFile:
    """Return a sanitised PNG ``ContentFile`` or raise ``UploadError``. Used where an image
    still arrives through Django (a staff tool), not the customer upload path."""
    _, image = _inspect(
        uploaded_file,
        getattr(settings, "DESIGN_UPLOAD_MAX_BYTES", 15 * 1024 * 1024),
        getattr(settings, "DESIGN_UPLOAD_MAX_DIMENSION", 8000),
    )
    return ContentFile(_reencode_png(image), name="design.png")


def validate_product_image(uploaded_file) -> None:
    """Run the same checks on an admin-uploaded product photo, but keep the original
    encoding: re-encoding studio JPEGs to PNG would multiply their served size."""
    _inspect(
        uploaded_file,
        getattr(settings, "PRODUCT_IMAGE_MAX_BYTES", 15 * 1024 * 1024),
        getattr(settings, "DESIGN_UPLOAD_MAX_DIMENSION", 8000),
    )
    uploaded_file.seek(0)


def sanitise_upload(design) -> str:
    """Fetch a raw upload from private R2, validate and re-encode it to a clean print-ready
    PNG written back to R2, then delete the raw file (M7.3). Records the real dimensions and
    a coarse DPI, and flags a low-resolution raster for review. Never raises: a bad upload is
    recorded as ``failed`` so the row stays visible. Returns a short result string."""
    from .models import DesignUpload

    max_bytes = getattr(settings, "DESIGN_UPLOAD_MAX_BYTES", 15 * 1024 * 1024)
    max_dim = getattr(settings, "DESIGN_UPLOAD_MAX_DIMENSION", 8000)
    try:
        raw = r2.read_bytes(design.r2_key_raw)
        raw, image = _inspect_bytes(raw, max_bytes, max_dim)
    except (UploadError, FileNotFoundError, OSError) as exc:
        design.status = DesignUpload.Status.FAILED
        design.review_status = DesignUpload.ReviewStatus.REJECTED
        design.review_reason = getattr(exc, "message", str(exc))[:200]
        design.save(update_fields=["status", "review_status", "review_reason", "updated_at"])
        return "failed"

    key_print = r2.print_key()
    r2.write_bytes(key_print, _reencode_png(image))

    longest = max(image.width, image.height)
    dpi = int(longest / NOMINAL_PRINT_INCHES) if longest else 0

    design.r2_key_print = key_print
    design.mime = "image/png"
    design.bytes = len(raw)
    design.width_px = image.width
    design.height_px = image.height
    design.dpi_estimate = dpi
    design.status = DesignUpload.Status.READY
    design.sanitised_at = timezone.now()
    design.review_status = (
        DesignUpload.ReviewStatus.FLAGGED
        if dpi < MIN_PRINT_DPI
        else DesignUpload.ReviewStatus.AUTO_OK
    )
    # The raw upload has done its job; only the clean raster is retained (§8).
    r2.delete(design.r2_key_raw)
    design.r2_key_raw = ""
    design.save(
        update_fields=[
            "r2_key_raw",
            "r2_key_print",
            "mime",
            "bytes",
            "width_px",
            "height_px",
            "dpi_estimate",
            "status",
            "sanitised_at",
            "review_status",
            "updated_at",
        ]
    )
    return "ready"

"""Private object storage (Cloudflare R2) helper for customer artwork.

Everything customer-uploaded lives in the ``designs`` storage, which is a private R2 bucket
in production and on-disk locally, so the same code path works offline. Keys are always
random UUIDs, never a customer filename, which is both an enumeration guard and a stored-XSS
guard (rebuild/03-architecture.md §8).

The browser PUTs raw bytes straight to a presigned URL; Django never receives them (Vercel's
4.5 MB body cap). Qikink later fetches the print-ready file through a short-lived signed GET.
"""

from __future__ import annotations

import uuid

from django.core.files.base import ContentFile
from django.core.files.storage import storages
from django.urls import reverse


def _storage():
    return storages["designs"]


def raw_key(ext: str = "bin") -> str:
    return f"designs/raw/{uuid.uuid4().hex}.{ext}"


def print_key() -> str:
    return f"designs/print/{uuid.uuid4().hex}.png"


def mockup_key() -> str:
    return f"designs/mockup/{uuid.uuid4().hex}.png"


def read_bytes(key: str) -> bytes:
    with _storage().open(key, "rb") as handle:
        return handle.read()


def write_bytes(key: str, data: bytes) -> str:
    """Write bytes at exactly ``key`` (no storage-side suffixing), overwriting if present."""
    storage = _storage()
    if storage.exists(key):
        storage.delete(key)
    return storage.save(key, ContentFile(data))


def delete(key: str) -> None:
    if key and _storage().exists(key):
        _storage().delete(key)


def exists(key: str) -> bool:
    return bool(key) and _storage().exists(key)


def signed_get_url(key: str, expires: int | None = None) -> str:
    """A time-limited GET URL for the object. On R2 this is a signed link; locally it is the
    storage's plain URL. ``expires`` is honoured only by the S3 backend."""
    storage = _storage()
    if not key:
        return ""
    try:
        return storage.url(key, expire=expires)
    except TypeError:
        return storage.url(key)


def presigned_put(key: str, content_type: str, expires: int = 300) -> str:
    """A URL the browser can PUT ``content_type`` bytes to for ``expires`` seconds.

    On R2 this is a presigned S3 ``put_object`` URL. Locally, where there is no object store,
    it points at the dev-only receiver that writes into the ``designs`` storage, so the whole
    upload path is exercisable under ``runserver``."""
    storage = _storage()
    connection = getattr(storage, "connection", None)
    bucket_name = getattr(storage, "bucket_name", None)
    if connection is not None and bucket_name:
        client = connection.meta.client
        return client.generate_presigned_url(
            "put_object",
            Params={"Bucket": bucket_name, "Key": key, "ContentType": content_type},
            ExpiresIn=expires,
        )
    return f"{reverse('designs-dev-upload')}?key={key}"

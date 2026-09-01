"""S3/R2 storage switch — STORAGES["default"] flips on S3_BUCKET_NAME (plan.md §8).

Settings are module-level code, so each case imports a *fresh copy* of
``config.settings.base`` under a throwaway name with the env patched — the live test
settings are never touched.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

BASE_PY = Path(__file__).resolve().parents[3] / "config" / "settings" / "base.py"


def _load_base(monkeypatch, **env):
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    spec = importlib.util.spec_from_file_location("_settings_probe", BASE_PY)
    module = importlib.util.module_from_spec(spec)
    sys.modules["_settings_probe"] = module
    try:
        spec.loader.exec_module(module)
    finally:
        del sys.modules["_settings_probe"]
    return module


def test_no_bucket_uses_local_disk(monkeypatch):
    cfg = _load_base(monkeypatch, S3_BUCKET_NAME="")
    assert cfg.STORAGES["default"]["BACKEND"] == "django.core.files.storage.FileSystemStorage"


def test_bucket_switches_to_private_signed_s3(monkeypatch):
    cfg = _load_base(
        monkeypatch,
        S3_BUCKET_NAME="test-bucket",
        S3_ACCESS_KEY_ID="test-access-key",
        S3_SECRET_ACCESS_KEY="test-secret-key",
        S3_SIGNED_URL_TTL="600",
    )
    default = cfg.STORAGES["default"]
    assert default["BACKEND"] == "storages.backends.s3.S3Storage"
    opts = default["OPTIONS"]
    assert opts["bucket_name"] == "test-bucket"
    assert opts["default_acl"] == "private"
    assert opts["querystring_auth"] is True  # signed URLs, never public
    assert opts["querystring_expire"] == 600
    assert opts["file_overwrite"] is False


def test_offline_mode_forces_local_disk(settings):
    # This suite runs under USE_SQLITE=1 — offline mode must be on local disk even
    # when the developer's .env configures a bucket.
    assert settings.STORAGES["default"]["BACKEND"] == "django.core.files.storage.FileSystemStorage"

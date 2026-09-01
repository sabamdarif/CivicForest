"""Production file storage: customer artwork must never be publicly readable.

Settings are module-level code, so each case reimports ``config.settings.production``
with the environment patched. ``base`` is reimported alongside it, since that is where
the S3 variables are read. The live test settings are never touched.
"""

from __future__ import annotations

import importlib
import sys

_SETTINGS_MODULES = ("config.settings.base", "config.settings.production")

REQUIRED_ENV = {
    "DJANGO_SECRET_KEY": "probe-secret-key",
    "DATABASE_URL": "postgres://u:p@example.neon.tech/db",
    "S3_BUCKET_NAME": "test-bucket",
    "S3_ACCESS_KEY_ID": "test-access-key",
    "S3_SECRET_ACCESS_KEY": "test-secret-key",
    "S3_ENDPOINT_URL": "https://acct.r2.cloudflarestorage.com",
}


def _load_production(monkeypatch, **extra_env):
    for key, value in {**REQUIRED_ENV, **extra_env}.items():
        monkeypatch.setenv(key, value)
    saved = {name: sys.modules.pop(name, None) for name in _SETTINGS_MODULES}
    try:
        return importlib.import_module("config.settings.production")
    finally:
        for name, module in saved.items():
            sys.modules.pop(name, None)
            if module is not None:
                sys.modules[name] = module


def test_media_goes_to_r2_behind_signed_urls(monkeypatch):
    cfg = _load_production(monkeypatch, S3_SIGNED_URL_TTL="600")
    default = cfg.STORAGES["default"]
    assert default["BACKEND"] == "storages.backends.s3.S3Storage"
    opts = default["OPTIONS"]
    assert opts["bucket_name"] == "test-bucket"
    assert opts["endpoint_url"] == "https://acct.r2.cloudflarestorage.com"
    assert opts["querystring_auth"] is True  # signed URLs, never public
    assert opts["querystring_expire"] == 600
    assert opts["default_acl"] is None  # R2 has no object ACLs
    assert opts["file_overwrite"] is False


def test_static_files_are_hashed_for_the_cdn(monkeypatch):
    cfg = _load_production(monkeypatch)
    assert cfg.STORAGES["staticfiles"]["BACKEND"] == (
        "django.contrib.staticfiles.storage.ManifestStaticFilesStorage"
    )


def test_local_and_test_settings_stay_on_disk(settings):
    # No bucket credentials exist offline, and no test should reach the network.
    assert settings.STORAGES["default"]["BACKEND"] == "django.core.files.storage.FileSystemStorage"

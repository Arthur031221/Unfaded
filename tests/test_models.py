import hashlib

import pytest

from unfaded import models


def test_every_model_is_pinned():
    for spec in models.REGISTRY.values():
        assert len(spec.sha256) == 64 and spec.url.startswith("https://")
        assert spec.size > 0 and spec.license


def test_steps_map_to_known_models():
    for keys in models.STEP_MODELS.values():
        assert set(keys) <= set(models.REGISTRY)


def test_cache_dir_follows_the_environment(tmp_path):
    assert models.cache_dir() == tmp_path / "home" / "models"


def test_status_reports_missing_weights():
    assert not any(row["installed"] for row in models.status())


def test_a_download_with_a_wrong_checksum_is_discarded(tmp_path, monkeypatch):
    payload = b"not the real weights"
    src = tmp_path / "served.bin"
    src.write_bytes(payload)
    spec = models.REGISTRY["face_detect"]
    fake = models.ModelSpec(
        spec.key, spec.filename, src.as_uri(), hashlib.sha256(b"other").hexdigest(), len(payload),
        spec.purpose, spec.license, spec.source,
    )  # fmt: skip
    monkeypatch.setitem(models.REGISTRY, "face_detect", fake)
    with pytest.raises(RuntimeError, match="checksum"):
        models.ensure("face_detect")
    assert not models.model_path("face_detect").exists()
    assert not list(models.cache_dir().glob("*.part"))


def test_a_good_download_is_kept(tmp_path, monkeypatch):
    payload = b"tiny model"
    src = tmp_path / "served.bin"
    src.write_bytes(payload)
    spec = models.REGISTRY["face_detect"]
    fake = models.ModelSpec(
        spec.key, spec.filename, src.as_uri(), hashlib.sha256(payload).hexdigest(), len(payload),
        spec.purpose, spec.license, spec.source,
    )  # fmt: skip
    monkeypatch.setitem(models.REGISTRY, "face_detect", fake)
    path = models.ensure("face_detect")
    assert path.read_bytes() == payload and models.is_installed("face_detect")


def test_a_cached_file_that_changed_is_rejected(tmp_path, monkeypatch):
    payload = b"tiny model"
    src = tmp_path / "served.bin"
    src.write_bytes(payload)
    spec = models.REGISTRY["face_detect"]
    fake = models.ModelSpec(
        spec.key, spec.filename, src.as_uri(), hashlib.sha256(payload).hexdigest(), len(payload),
        spec.purpose, spec.license, spec.source,
    )  # fmt: skip
    monkeypatch.setitem(models.REGISTRY, "face_detect", fake)
    path = models.ensure("face_detect")
    assert models.ensure("face_detect") == path  # second call trusts the remembered check
    path.write_bytes(b"tampered!!")  # same size, different content
    with pytest.raises(RuntimeError, match="checksum"):
        models.ensure("face_detect")

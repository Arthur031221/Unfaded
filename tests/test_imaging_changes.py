import cv2
import numpy as np
import pytest

from unfaded import changes, fade, imaging, synth


def test_grayscale_detection():
    gray = np.repeat(np.arange(256, dtype=np.uint8)[None, :, None], 3, axis=2)
    assert imaging.is_grayscale(gray)
    tinted = gray.copy()
    tinted[..., 0] = np.clip(tinted[..., 0].astype(int) + 60, 0, 255)
    assert not imaging.is_grayscale(tinted)


def test_fit_long_side_keeps_aspect_and_never_enlarges():
    img = np.zeros((400, 800, 3), np.uint8)
    assert imaging.fit_long_side(img, 200).shape[:2] == (100, 200)
    assert imaging.fit_long_side(img, 2000).shape[:2] == (400, 800)


def test_encode_and_load_round_trip():
    img = np.random.default_rng(0).integers(0, 255, (32, 48, 3), dtype=np.uint8)
    back = imaging.load_rgb(imaging.encode(img, ".png"))
    assert np.array_equal(img, back)


def test_load_rgb_honours_missing_file(tmp_path):
    with pytest.raises(FileNotFoundError):
        imaging.load_rgb(tmp_path / "missing.jpg")


def test_change_mask_is_zero_for_identical_images(portrait):
    mask = changes.change_mask(portrait, portrait)
    assert mask.max() == 0
    assert changes.changed_fraction(mask) == 0


def test_change_mask_sees_a_patch_and_handles_size_changes(portrait):
    after = portrait.copy()
    after[50:150, 50:150] = 255 - after[50:150, 50:150]
    mask = changes.change_mask(portrait, after)
    assert 0.0 < changes.changed_fraction(mask) < 0.2
    bigger = cv2.resize(after, None, fx=2, fy=2)
    assert changes.change_mask(portrait, bigger).shape == bigger.shape[:2]


def test_heat_overlay_keeps_image_size(portrait):
    mask = np.zeros(portrait.shape[:2], np.float32)
    mask[:20] = 1.0
    out = changes.heat_overlay(portrait, mask)
    assert out.shape == portrait.shape and out.dtype == np.uint8
    hot, cold = out[:10].astype(int), out[-10:].astype(int)
    assert np.abs(hot[..., 0] - hot[..., 2]).mean() > 20  # coloured where the mask is set
    assert np.abs(cold[..., 0] - cold[..., 2]).mean() < 2  # still grey elsewhere


def test_mask_png_is_decodable():
    mask = np.zeros((20, 30), np.float32)
    mask[5:10] = 1
    data = changes.mask_to_png_bytes(mask)
    decoded = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_GRAYSCALE)
    assert decoded.shape == (20, 30) and decoded[7, 3] == 255 and decoded[0, 0] == 0


def test_damage_is_reproducible_and_reports_its_mask(portrait):
    a, mask_a = synth.add_damage(portrait, seed=9)
    b, mask_b = synth.add_damage(portrait, seed=9)
    assert np.array_equal(a, b) and np.array_equal(mask_a, mask_b)
    assert 0.001 < (mask_a > 0).mean() < 0.15
    assert not np.array_equal(a, portrait)


def test_fade_recovery_stretches_a_flat_print():
    ramp = np.linspace(100, 160, 256, dtype=np.float32)[None, :].repeat(64, axis=0)
    flat = np.repeat(ramp[..., None], 3, axis=2).astype(np.uint8)
    out = fade.recover(flat, grayscale=True)
    assert out.min() < 10 and out.max() > 245


def test_fade_recovery_removes_a_colour_cast():
    rng = np.random.default_rng(1)
    base = rng.integers(60, 200, (64, 64, 1), dtype=np.uint8).repeat(3, axis=2).astype(np.int32)
    cast = np.clip(base + np.array([40, 10, -30]), 0, 255).astype(np.uint8)
    out = fade.recover(cast, grayscale=False).astype(float)
    assert abs(out[..., 0].mean() - out[..., 2].mean()) < abs(cast[..., 0].mean() - cast[..., 2].mean())

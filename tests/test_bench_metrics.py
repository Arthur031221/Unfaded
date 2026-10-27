import numpy as np

from unfaded import bench


def test_psnr_of_identical_images_is_capped():
    img = np.full((8, 8, 3), 100, np.uint8)
    assert bench.psnr(img, img) == 99.0


def test_psnr_matches_the_definition():
    a = np.zeros((4, 4, 3), np.uint8)
    b = np.full((4, 4, 3), 10, np.uint8)
    assert abs(bench.psnr(a, b) - 10 * np.log10(255**2 / 100)) < 1e-9


def test_psnr_can_be_restricted_to_a_region():
    a = np.zeros((4, 4, 3), np.uint8)
    b = a.copy()
    b[0, 0] = 255
    where = np.zeros((4, 4), np.uint8)
    where[1:, 1:] = 1
    assert bench.psnr(a, b, where) == 99.0
    assert bench.psnr(a, b) < 30


def test_ssim_is_one_for_equal_images_and_lower_for_noise(portrait):
    assert abs(bench.ssim(portrait, portrait) - 1.0) < 1e-9
    noisy = np.clip(portrait + np.random.default_rng(0).normal(0, 25, portrait.shape), 0, 255).astype(np.uint8)
    assert bench.ssim(portrait, noisy) < 0.9


def test_quad_iou():
    square = np.array([[0, 0], [10, 0], [10, 10], [0, 10]], np.float32)
    assert bench.quad_iou(square, square, (20, 20)) == 1.0
    far = square + 100
    assert bench.quad_iou(square, far, (200, 200)) == 0.0


def test_default_images_are_the_bundled_examples():
    names = {p.name for p in bench.default_images()}
    assert "king-family.jpg" in names

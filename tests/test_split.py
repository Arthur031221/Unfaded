import numpy as np

from unfaded import split
from unfaded.bench import quad_iou


def test_finds_every_print_on_a_scan(scan):
    image, truth = scan
    quads = split.detect(image)
    assert len(quads) == len(truth)
    for expected in truth:
        best = max(quad_iou(q.as_array(), expected, image.shape[:2]) for q in quads)
        assert best > 0.9


def test_blank_page_has_no_prints():
    page = np.full((800, 600, 3), 245, np.uint8)
    assert split.detect(page) == []


def test_order_corners_is_clockwise_from_top_left():
    pts = np.array([[90, 80], [10, 10], [10, 80], [90, 10]], np.float32)
    ordered = split.order_corners(pts)
    assert ordered.tolist() == [[10, 10], [90, 10], [90, 80], [10, 80]]


def test_quad_round_trips_through_json():
    quad = split.Quad(np.array([[0, 0], [10, 0], [10, 5], [0, 5]], np.float32), 0.9)
    again = split.Quad.from_json(quad.to_json())
    assert np.allclose(again.as_array(), quad.as_array())
    assert again.score == quad.score


def test_warp_returns_an_upright_crop(scan):
    image, _ = scan
    quad = split.detect(image)[0]
    crop = split.warp(image, quad)
    assert crop.ndim == 3 and crop.shape[2] == 3
    assert min(crop.shape[:2]) > 100


def test_rotate_quarter():
    img = np.zeros((10, 20, 3), np.uint8)
    assert split.rotate_quarter(img, 1).shape[:2] == (20, 10)
    assert split.rotate_quarter(img, 4).shape[:2] == (10, 20)

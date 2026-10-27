"""Synthetic scans and synthetic damage, for tests and the benchmark.

Every random choice comes from a seeded generator so a number printed in the
docs can be reproduced exactly.
"""

from __future__ import annotations

import cv2
import numpy as np


def compose_scan(
    prints: list[np.ndarray],
    size: tuple[int, int] = (2200, 1600),
    background: tuple[int, int, int] = (246, 246, 244),
    angles: list[float] | None = None,
    seed: int = 7,
) -> tuple[np.ndarray, list[np.ndarray]]:
    """Place prints on a flatbed background. Returns the scan and each print's true corners."""
    rng = np.random.default_rng(seed)
    width, height = size
    scan = np.full((height, width, 3), background, np.uint8)
    cols = 2 if len(prints) > 1 else 1
    rows = -(-len(prints) // cols)
    cell_w, cell_h = width // cols, height // rows
    truth = []
    for i, photo in enumerate(prints):
        fit = min(cell_w * 0.78 / photo.shape[1], cell_h * 0.78 / photo.shape[0])
        small = cv2.resize(photo, None, fx=fit, fy=fit, interpolation=cv2.INTER_AREA)
        h, w = small.shape[:2]
        angle = angles[i] if angles else float(rng.uniform(-9, 9))
        cx, cy = (i % cols + 0.5) * cell_w, (i // cols + 0.5) * cell_h
        matrix = cv2.getRotationMatrix2D((w / 2, h / 2), angle, 1.0)
        matrix[:, 2] += (cx - w / 2, cy - h / 2)
        layer = cv2.warpAffine(small, matrix, (width, height), borderValue=(0, 0, 0))
        cover = cv2.warpAffine(np.full((h, w), 255, np.uint8), matrix, (width, height))
        shadow = cv2.GaussianBlur(np.roll(cover, (6, 6), axis=(0, 1)), (0, 0), 5)
        scan = (scan * (1 - 0.22 * shadow[..., None] / 255.0)).astype(np.uint8)
        scan = np.where(cover[..., None] > 127, layer, scan)
        corners = np.array([[0, 0], [w, 0], [w, h], [0, h]], np.float32)
        truth.append(cv2.transform(corners[None], matrix)[0])
    noise = rng.normal(0, 1.2, scan.shape)
    return np.clip(scan + noise, 0, 255).astype(np.uint8), truth


def add_damage(
    rgb: np.ndarray, seed: int = 3, scratches: int = 14, creases: int = 2, dust: int = 120, fade: float = 0.0
) -> tuple[np.ndarray, np.ndarray]:
    """Draw scratches, creases and dust onto a clean image. Returns the image and the true mask."""
    rng = np.random.default_rng(seed)
    h, w = rgb.shape[:2]
    out = rgb.astype(np.float32)
    mask = np.zeros((h, w), np.uint8)
    layer = np.zeros((h, w), np.float32)
    thin = max(1, round(min(h, w) / 700))

    def curve(length: float, wobble: float) -> np.ndarray:
        x0, y0 = rng.uniform(0, w), rng.uniform(0, h)
        angle = rng.uniform(0, np.pi)
        t = np.linspace(0, length, 40)
        bend = np.cumsum(rng.normal(0, wobble, t.size))
        xs = x0 + t * np.cos(angle) + bend * np.sin(angle)
        ys = y0 + t * np.sin(angle) - bend * np.cos(angle)
        return np.stack([xs, ys], axis=1).astype(np.int32)

    for _ in range(scratches):
        pts = curve(rng.uniform(0.15, 0.6) * min(h, w), 1.5)
        shade = 255.0 if rng.random() < 0.7 else 0.0
        cv2.polylines(layer, [pts], False, 1.0, thin + int(rng.integers(0, 2)), cv2.LINE_AA)
        cv2.polylines(mask, [pts], False, 255, thin + 2)
        out = np.where(layer[..., None] > 0.2, out * 0.25 + shade * 0.75, out)
        layer[:] = 0
    for _ in range(creases):
        pts = curve(rng.uniform(0.5, 0.9) * min(h, w), 3.0)
        width = thin * 3
        cv2.polylines(layer, [pts], False, 1.0, width, cv2.LINE_AA)
        cv2.polylines(mask, [pts], False, 255, width + 2)
        soft = cv2.GaussianBlur(layer, (0, 0), width)
        out = out + soft[..., None] * 70.0 - 10.0 * soft[..., None]
        out = np.where(layer[..., None] > 0.3, out * 0.35 + 255.0 * 0.65, out)
        layer[:] = 0
    for _ in range(dust):
        x, y = int(rng.integers(0, w)), int(rng.integers(0, h))
        radius = int(rng.integers(1, 1 + 2 * thin))
        shade = 245.0 if rng.random() < 0.6 else 15.0
        cv2.circle(mask, (x, y), radius + 1, 255, -1)
        cv2.circle(out, (x, y), radius, (shade, shade, shade), -1, cv2.LINE_AA)
    if fade > 0:
        out = out * (1 - fade) + 128.0 * fade
    return np.clip(out, 0, 255).astype(np.uint8), mask

"""Find the prints on a flatbed scan, then cut each one out straight.

The detector is classical on purpose: it needs no weights, runs in
milliseconds and its failures are easy to see and fix with the corner handles.
"""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

WORK_SIZE = 1400
MIN_FILL = 0.5  # a ring-shaped blob along the scan edge is background noise, not a print
MIN_DISTANCE = 9.0
EDGE_LEVEL = 14.0


@dataclass
class Quad:
    """Four corners in source pixels, ordered top left, top right, bottom right, bottom left."""

    points: list[tuple[float, float]]
    score: float = 1.0

    def as_array(self) -> np.ndarray:
        return np.array(self.points, dtype=np.float32)

    def area(self) -> float:
        return float(cv2.contourArea(self.as_array()))

    def to_json(self) -> dict:
        return {"points": [[round(x, 1), round(y, 1)] for x, y in self.points], "score": self.score}

    @classmethod
    def from_json(cls, data: dict) -> Quad:
        return cls([(float(x), float(y)) for x, y in data["points"]], float(data.get("score", 1.0)))


def order_corners(pts: np.ndarray) -> np.ndarray:
    pts = np.asarray(pts, dtype=np.float32).reshape(4, 2)
    total = pts.sum(axis=1)
    diff = pts[:, 0] - pts[:, 1]
    return np.array(
        [pts[np.argmin(total)], pts[np.argmax(diff)], pts[np.argmax(total)], pts[np.argmin(diff)]],
        dtype=np.float32,
    )


def _background_lab(lab: np.ndarray) -> np.ndarray:
    h, w = lab.shape[:2]
    band = max(2, round(min(h, w) * 0.02))
    edge = np.concatenate(
        [
            lab[:band].reshape(-1, 3),
            lab[-band:].reshape(-1, 3),
            lab[:, :band].reshape(-1, 3),
            lab[:, -band:].reshape(-1, 3),
        ]
    )
    return np.median(edge, axis=0)


def _foreground(small: np.ndarray) -> np.ndarray:
    lab = cv2.cvtColor(small, cv2.COLOR_RGB2LAB).astype(np.float32)
    dist = np.linalg.norm(lab - _background_lab(lab), axis=2)
    dist = cv2.GaussianBlur(dist, (0, 0), 1.5)
    scaled = np.clip(dist * (255.0 / max(dist.max(), 1.0)), 0, 255).astype(np.uint8)
    otsu, _ = cv2.threshold(scaled, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    limit = max(MIN_DISTANCE, otsu * dist.max() / 255.0 * 0.6)
    mask = (dist > limit).astype(np.uint8) * 255
    # A paper edge on a white lid has almost no colour contrast, so its outline is
    # added from the gradient and closed into a shape before the holes are filled.
    gray = cv2.GaussianBlur(lab[..., 0], (0, 0), 1.2)
    gx, gy = cv2.Sobel(gray, cv2.CV_32F, 1, 0), cv2.Sobel(gray, cv2.CV_32F, 0, 1)
    edges = (np.hypot(gx, gy) > EDGE_LEVEL).astype(np.uint8) * 255
    mask = cv2.bitwise_or(mask, edges)
    k = max(3, round(min(small.shape[:2]) * 0.012) | 1)
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k))
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    filled = np.zeros_like(mask)
    cv2.drawContours(filled, contours, -1, 255, thickness=cv2.FILLED)
    return filled


def _fill_ratio(contour: np.ndarray) -> tuple[float, np.ndarray]:
    rect = cv2.minAreaRect(contour)
    box = cv2.boxPoints(rect)
    return cv2.contourArea(contour) / max(rect[1][0] * rect[1][1], 1.0), box


def _separate_touching(mask: np.ndarray, min_area: float) -> list[np.ndarray]:
    """Split a blob made of touching prints by eroding until it falls apart."""
    for steps in range(2, 40, 2):
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * steps + 1, 2 * steps + 1))
        core = cv2.erode(mask, kernel)
        count, labels = cv2.connectedComponents(core)
        if count - 1 < 2:
            continue
        parts = []
        for index in range(1, count):
            part = (labels == index).astype(np.uint8) * 255
            if cv2.countNonZero(part) < min_area * 0.3:
                continue
            part = cv2.dilate(part, kernel)
            parts.append(cv2.bitwise_and(part, mask))
        if len(parts) >= 2:
            contours = []
            for part in parts:
                found, _ = cv2.findContours(part, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                contours.extend(found)
            return contours
    return []


def detect(rgb: np.ndarray, min_area_fraction: float = 0.02, max_photos: int = 24) -> list[Quad]:
    h, w = rgb.shape[:2]
    scale = min(1.0, WORK_SIZE / max(h, w))
    small = cv2.resize(rgb, (round(w * scale), round(h * scale)), interpolation=cv2.INTER_AREA)
    mask = _foreground(small)
    min_area = small.shape[0] * small.shape[1] * min_area_fraction
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    quads: list[Quad] = []
    for contour in contours:
        if cv2.contourArea(contour) < min_area:
            continue
        fill, box = _fill_ratio(contour)
        candidates = [(contour, fill, box)]
        if fill < 0.82:
            blob = np.zeros_like(mask)
            cv2.drawContours(blob, [contour], -1, 255, thickness=cv2.FILLED)
            pieces = _separate_touching(blob, min_area)
            if pieces:
                candidates = [(c, *_fill_ratio(c)) for c in pieces if cv2.contourArea(c) >= min_area]
        for _, ratio, corners in candidates:
            if ratio < MIN_FILL:
                continue
            points = [(float(x) / scale, float(y) / scale) for x, y in order_corners(corners)]
            quads.append(Quad(points, round(ratio, 3)))
    quads.sort(key=lambda q: (round(min(p[1] for p in q.points) / (h / 6)), min(p[0] for p in q.points)))
    return quads[:max_photos]


def covers_whole_image(quad: Quad, shape: tuple[int, ...], tolerance: float = 0.9) -> bool:
    h, w = shape[:2]
    return quad.area() >= tolerance * h * w


def warp(rgb: np.ndarray, quad: Quad, inset: float = 0.008) -> np.ndarray:
    src = order_corners(quad.as_array())
    top, bottom = np.linalg.norm(src[1] - src[0]), np.linalg.norm(src[2] - src[3])
    left, right = np.linalg.norm(src[3] - src[0]), np.linalg.norm(src[2] - src[1])
    width, height = max(round(max(top, bottom)), 8), max(round(max(left, right)), 8)
    dst = np.array([[0, 0], [width - 1, 0], [width - 1, height - 1], [0, height - 1]], np.float32)
    matrix = cv2.getPerspectiveTransform(src, dst)
    out = cv2.warpPerspective(rgb, matrix, (width, height), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
    cut = round(min(width, height) * inset)
    if cut > 0 and min(width, height) > 4 * cut:
        out = out[cut : height - cut, cut : width - cut]
    return np.ascontiguousarray(out)


def rotate_quarter(rgb: np.ndarray, turns: int) -> np.ndarray:
    return np.ascontiguousarray(np.rot90(rgb, k=-(turns % 4)))

"""What did a step change? A per pixel map, a heat overlay and one summary number."""

from __future__ import annotations

import cv2
import numpy as np

SATURATE = 40.0
COUNTED = 0.12


def change_mask(before: np.ndarray, after: np.ndarray) -> np.ndarray:
    """Float map in [0, 1]. Sizes may differ: ``before`` is resized to ``after``."""
    if before.shape[:2] != after.shape[:2]:
        before = cv2.resize(before, (after.shape[1], after.shape[0]), interpolation=cv2.INTER_CUBIC)
    a = cv2.cvtColor(before, cv2.COLOR_RGB2LAB).astype(np.float32)
    b = cv2.cvtColor(after, cv2.COLOR_RGB2LAB).astype(np.float32)
    delta = np.sqrt(((a - b) ** 2).sum(axis=2))
    delta = cv2.GaussianBlur(delta, (0, 0), 0.8)
    return np.clip(delta / SATURATE, 0.0, 1.0)


def changed_fraction(mask: np.ndarray) -> float:
    return float((mask > COUNTED).mean())


def heat_overlay(base: np.ndarray, mask: np.ndarray, opacity: float = 0.75) -> np.ndarray:
    """Paint the change map over ``base`` (resized to the mask when needed)."""
    if base.shape[:2] != mask.shape[:2]:
        base = cv2.resize(base, (mask.shape[1], mask.shape[0]), interpolation=cv2.INTER_AREA)
    heat = cv2.applyColorMap((mask * 255).astype(np.uint8), cv2.COLORMAP_INFERNO)
    heat = cv2.cvtColor(heat, cv2.COLOR_BGR2RGB)
    gray = cv2.cvtColor(base, cv2.COLOR_RGB2GRAY)
    dim = np.repeat((gray * 0.55)[..., None], 3, axis=2)
    weight = (np.clip(mask * 3.0, 0, 1) * opacity)[..., None]
    return (dim * (1 - weight) + heat * weight).astype(np.uint8)


def mask_to_png_bytes(mask: np.ndarray) -> bytes:
    ok, buf = cv2.imencode(".png", (mask * 255).astype(np.uint8))
    if not ok:
        raise ValueError("could not encode mask")
    return buf.tobytes()

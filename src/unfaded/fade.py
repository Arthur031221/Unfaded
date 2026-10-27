"""Tone and colour recovery for faded prints. Plain image maths, no model."""

from __future__ import annotations

import cv2
import numpy as np


def recover(rgb: np.ndarray, grayscale: bool, low: float = 0.4, high: float = 99.6) -> np.ndarray:
    """Stretch levels, remove the dominant cast and bring back lost saturation.

    A black and white print keeps one shared stretch so a sepia or yellow tint is
    neutralised without inventing colour. A colour print is stretched per channel,
    which undoes the uneven dye fading seen on 1970s prints.
    """
    img = rgb.astype(np.float32)
    if grayscale:
        lum = img.mean(axis=2)
        lo, hi = np.percentile(lum, [low, high])
        gray = np.clip((lum - lo) / max(hi - lo, 1.0), 0, 1) * 255.0
        return np.repeat(gray[..., None], 3, axis=2).astype(np.uint8)
    out = np.empty_like(img)
    for c in range(3):
        lo, hi = np.percentile(img[..., c], [low, high])
        out[..., c] = np.clip((img[..., c] - lo) / max(hi - lo, 1.0), 0, 1) * 255.0
    lab = cv2.cvtColor(out.astype(np.uint8), cv2.COLOR_RGB2LAB).astype(np.float32)
    chroma = lab[..., 1:] - 128.0
    cast = np.median(chroma.reshape(-1, 2), axis=0)
    chroma = chroma - 0.6 * cast
    mean_chroma = float(np.hypot(chroma[..., 0], chroma[..., 1]).mean())
    gain = float(np.clip(18.0 / max(mean_chroma, 1.0), 1.0, 1.8))
    lab[..., 1:] = np.clip(chroma * gain + 128.0, 0, 255)
    return cv2.cvtColor(lab.astype(np.uint8), cv2.COLOR_LAB2RGB)

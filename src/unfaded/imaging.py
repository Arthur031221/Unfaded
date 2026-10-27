"""Image loading and saving. Everything inside the pipeline is RGB uint8."""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageOps

Image.MAX_IMAGE_PIXELS = 400_000_000


def load_rgb(source: str | Path | bytes) -> np.ndarray:
    import io

    handle = io.BytesIO(source) if isinstance(source, bytes) else source
    with Image.open(handle) as img:
        img = ImageOps.exif_transpose(img)
        if img.mode in ("I;16", "I;16B", "I"):
            arr = np.asarray(img, dtype=np.float32)
            arr = arr / max(float(arr.max()), 1.0) * 255.0
            return np.repeat(arr.astype(np.uint8)[..., None], 3, axis=2)
        return np.asarray(img.convert("RGB"))


def save(path: str | Path, rgb: np.ndarray, quality: int = 95) -> None:
    path = Path(path)
    img = Image.fromarray(rgb)
    if path.suffix.lower() in (".jpg", ".jpeg"):
        img.save(path, quality=quality, subsampling=0)
    else:
        img.save(path)


def encode(rgb: np.ndarray, ext: str = ".jpg", quality: int = 90) -> bytes:
    flag = [cv2.IMWRITE_JPEG_QUALITY, quality] if ext == ".jpg" else []
    ok, buf = cv2.imencode(ext, cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR), flag)
    if not ok:
        raise ValueError("could not encode image")
    return buf.tobytes()


def is_grayscale(rgb: np.ndarray, tolerance: float = 6.0) -> bool:
    """True when the colour channels carry almost no chroma (a black and white print)."""
    small = cv2.resize(rgb, (128, 128), interpolation=cv2.INTER_AREA).astype(np.int16)
    spread = small.max(axis=2) - small.min(axis=2)
    return float(spread.mean()) < tolerance


def fit_long_side(rgb: np.ndarray, size: int) -> np.ndarray:
    h, w = rgb.shape[:2]
    if max(h, w) <= size:
        return rgb
    scale = size / max(h, w)
    return cv2.resize(rgb, (round(w * scale), round(h * scale)), interpolation=cv2.INTER_AREA)

"""Fill the damage mask with LaMa, working on windows around each damaged area."""

from __future__ import annotations

import cv2
import numpy as np
import torch

from . import models
from .runtime import pick_device

CONTEXT = 96
MAX_WINDOW = 1280


class Inpainter:
    def __init__(self, device: str = "auto") -> None:
        self.device = pick_device(device)
        self.net = torch.jit.load(str(models.ensure("inpaint")), map_location=self.device).eval()

    @torch.inference_mode()
    def _run(self, rgb: np.ndarray, mask: np.ndarray) -> np.ndarray:
        h, w = rgb.shape[:2]
        pad_h, pad_w = (-h) % 8, (-w) % 8
        image = np.pad(rgb, ((0, pad_h), (0, pad_w), (0, 0)), mode="reflect")
        hole = np.pad(mask, ((0, pad_h), (0, pad_w)), mode="reflect")
        x = torch.from_numpy(image).permute(2, 0, 1)[None].float().div(255).to(self.device)
        m = torch.from_numpy((hole > 127).astype(np.float32))[None, None].to(self.device)
        out = self.net(x, m)[0].permute(1, 2, 0).clamp(0, 1).mul(255).byte().cpu().numpy()
        return out[:h, :w]

    def __call__(self, rgb: np.ndarray, mask: np.ndarray) -> np.ndarray:
        """Return ``rgb`` with the pixels where ``mask`` is 255 filled in. Other pixels are untouched."""
        if not mask.any():
            return rgb.copy()
        result = rgb.copy()
        for x0, y0, x1, y1 in _windows(mask):
            window = rgb[y0:y1, x0:x1]
            local = mask[y0:y1, x0:x1]
            filled = self._run(window, local)
            region = local > 127
            result[y0:y1, x0:x1][region] = filled[region]
        return result


def _windows(mask: np.ndarray) -> list[tuple[int, int, int, int]]:
    """Group the mask into windows with context, merging windows that overlap."""
    h, w = mask.shape
    joined = cv2.dilate(mask, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * CONTEXT // 2 + 1,) * 2))
    count, _, stats, _ = cv2.connectedComponentsWithStats((joined > 0).astype(np.uint8), connectivity=8)
    boxes = []
    for i in range(1, count):
        x, y, bw, bh = (int(stats[i, k]) for k in range(4))
        x0, y0 = max(0, x - CONTEXT // 2), max(0, y - CONTEXT // 2)
        x1, y1 = min(w, x + bw + CONTEXT // 2), min(h, y + bh + CONTEXT // 2)
        boxes.extend(_split(x0, y0, x1, y1))
    return boxes


def _split(x0: int, y0: int, x1: int, y1: int) -> list[tuple[int, int, int, int]]:
    """Cut a very large window into tiles that overlap by the context size."""
    if x1 - x0 <= MAX_WINDOW and y1 - y0 <= MAX_WINDOW:
        return [(x0, y0, x1, y1)]
    step = MAX_WINDOW - 2 * CONTEXT
    tiles = []
    for ty in range(y0, y1, step):
        for tx in range(x0, x1, step):
            left, top = max(x0, tx - CONTEXT), max(y0, ty - CONTEXT)
            tiles.append((left, top, min(x1, tx + step + CONTEXT), min(y1, ty + step + CONTEXT)))
    return tiles

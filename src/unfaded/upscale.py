"""Real-ESRGAN x4 with feathered tiles, so a large print does not need a large GPU."""

from __future__ import annotations

import cv2
import numpy as np
import torch

from . import models
from .runtime import free_memory, pick_device
from .vendor.esrgan.rrdbnet import RRDBNet

OVERLAP = 24


class Upscaler:
    def __init__(self, device: str = "auto", tile: int | None = None) -> None:
        self.device = pick_device(device)
        self.half = self.device.type == "cuda"
        self.tile = tile or (512 if self.device.type == "cuda" else 192)
        net = RRDBNet(num_in_ch=3, num_out_ch=3, num_feat=64, num_block=23, num_grow_ch=32, scale=4)
        state = torch.load(models.ensure("upscale"), map_location="cpu", weights_only=True)
        net.load_state_dict(state["params_ema"], strict=True)
        net = net.to(self.device).eval()
        self.net = net.half() if self.half else net

    @torch.inference_mode()
    def _tile(self, tile: np.ndarray) -> np.ndarray:
        x = torch.from_numpy(tile).permute(2, 0, 1)[None].float().div(255).to(self.device)
        out = self.net(x.half() if self.half else x)
        return out[0].float().clamp(0, 1).mul(255).permute(1, 2, 0).byte().cpu().numpy()

    def __call__(self, rgb: np.ndarray, scale: int = 4) -> np.ndarray:
        if scale not in (2, 4):
            raise ValueError("scale must be 2 or 4")
        h, w = rgb.shape[:2]
        acc = np.zeros((h * 4, w * 4, 3), np.float32)
        weight = np.zeros((h * 4, w * 4, 1), np.float32)
        step = self.tile - 2 * OVERLAP
        for y in range(0, h, step):
            for x in range(0, w, step):
                y0, x0 = max(0, y - OVERLAP), max(0, x - OVERLAP)
                y1, x1 = min(h, y + step + OVERLAP), min(w, x + step + OVERLAP)
                up = self._tile(rgb[y0:y1, x0:x1]).astype(np.float32)
                ramp = _ramp(up.shape[0], up.shape[1], OVERLAP * 4, y0 > 0, x0 > 0, y1 < h, x1 < w)
                acc[y0 * 4 : y1 * 4, x0 * 4 : x1 * 4] += up * ramp
                weight[y0 * 4 : y1 * 4, x0 * 4 : x1 * 4] += ramp
        free_memory()
        out = (acc / np.maximum(weight, 1e-6)).clip(0, 255).astype(np.uint8)
        if scale == 2:
            out = cv2.resize(out, (w * 2, h * 2), interpolation=cv2.INTER_AREA)
        return out


def _ramp(h: int, w: int, edge: int, top: bool, left: bool, bottom: bool, right: bool) -> np.ndarray:
    """Weights that fade towards the sides shared with a neighbouring tile."""
    fy, fx = np.ones(h, np.float32), np.ones(w, np.float32)
    fade = np.linspace(1e-3, 1.0, edge, dtype=np.float32)
    if top:
        fy[:edge] = fade
    if bottom:
        fy[-edge:] = fade[::-1]
    if left:
        fx[:edge] = fade
    if right:
        fx[-edge:] = fade[::-1]
    return (fy[:, None] * fx[None, :])[..., None]

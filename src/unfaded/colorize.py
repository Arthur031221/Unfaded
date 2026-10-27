"""Colorization with DDColor. The model predicts chroma only, so lightness is never changed."""

from __future__ import annotations

import cv2
import numpy as np
import torch
import torch.nn.functional as F

from . import models
from .runtime import pick_device
from .vendor.ddcolor.model import DDColor

INPUT_SIDE = 512


class Colorizer:
    def __init__(self, device: str = "auto") -> None:
        self.device = pick_device(device)
        net = DDColor(
            encoder_name="convnext-t",
            num_queries=100,
            num_scales=3,
            dec_layers=9,
            input_size=(INPUT_SIDE, INPUT_SIDE),
            num_output_channels=2,
            last_norm="Spectral",
        )
        state = torch.load(models.ensure("color"), map_location="cpu", weights_only=True)
        net.load_state_dict(state.get("params", state), strict=False)
        self.net = net.to(self.device).eval()

    @torch.inference_mode()
    def __call__(self, rgb: np.ndarray, strength: float = 1.0) -> np.ndarray:
        h, w = rgb.shape[:2]
        lab = cv2.cvtColor(rgb.astype(np.float32) / 255.0, cv2.COLOR_RGB2LAB)
        small = cv2.resize(rgb.astype(np.float32) / 255.0, (INPUT_SIDE, INPUT_SIDE))
        lightness = cv2.cvtColor(small, cv2.COLOR_RGB2LAB)[..., :1]
        flat = np.concatenate([lightness, np.zeros_like(lightness), np.zeros_like(lightness)], axis=-1)
        gray_rgb = cv2.cvtColor(flat, cv2.COLOR_LAB2RGB)
        x = torch.from_numpy(gray_rgb.transpose(2, 0, 1))[None].float().to(self.device)
        ab = self.net(x).float().cpu()
        ab = F.interpolate(ab, size=(h, w), mode="bilinear", align_corners=False)[0].numpy()
        out = np.concatenate([lab[..., :1], ab.transpose(1, 2, 0) * strength], axis=-1)
        return np.clip(cv2.cvtColor(out, cv2.COLOR_LAB2RGB) * 255.0, 0, 255).astype(np.uint8)

"""Scratch, crease and dust detection with the Microsoft old photo detector."""

from __future__ import annotations

import cv2
import numpy as np
import torch
import torch.nn.functional as F

from . import models
from .runtime import pick_device
from .vendor.bopbtl.networks import UNet

THRESHOLD = 0.4


class ScratchDetector:
    def __init__(self, device: str = "auto") -> None:
        self.device = pick_device(device)
        net = UNet(
            in_channels=1,
            out_channels=1,
            depth=4,
            conv_num=2,
            wf=6,
            padding=True,
            batch_norm=True,
            up_mode="upsample",
            with_tanh=False,
            sync_bn=False,
            antialiasing=True,
        )
        state = torch.load(models.ensure("scratch"), map_location="cpu", weights_only=True)
        net.load_state_dict(state["model_state"])
        self.net = net.to(self.device).eval()

    @torch.inference_mode()
    def _probability(self, gray: np.ndarray, short_side: int) -> np.ndarray:
        h, w = gray.shape
        scale = short_side / min(h, w)
        th, tw = (max(16, round(h * scale / 16) * 16), max(16, round(w * scale / 16) * 16))
        small = cv2.resize(gray, (tw, th), interpolation=cv2.INTER_AREA if scale < 1 else cv2.INTER_CUBIC)
        x = torch.from_numpy(small.astype(np.float32) / 127.5 - 1.0)[None, None].to(self.device)
        prob = torch.sigmoid(self.net(x))
        prob = F.interpolate(prob, size=(h, w), mode="bilinear", align_corners=False)
        return prob[0, 0].float().cpu().numpy()

    def detect(self, rgb: np.ndarray, scales: tuple[int, ...] = (512, 768)) -> np.ndarray:
        """Probability map in [0, 1]. Several scales catch both wide creases and fine hairlines."""
        gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
        short = min(gray.shape)
        used = sorted({min(s, short) for s in scales})
        return np.maximum.reduce([self._probability(gray, s) for s in used])


def probability_to_mask(prob: np.ndarray, grow: int = 2, min_pixels: int = 12) -> np.ndarray:
    """Binary uint8 mask (0 or 255) grown by ``grow`` pixels so the inpainting covers the halo."""
    mask = (prob >= THRESHOLD).astype(np.uint8)
    count, labels, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
    keep = np.zeros(count, bool)
    keep[1:] = stats[1:, cv2.CC_STAT_AREA] >= min_pixels
    mask = keep[labels].astype(np.uint8) * 255
    if grow > 0:
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * grow + 1, 2 * grow + 1))
        mask = cv2.dilate(mask, kernel)
    return mask

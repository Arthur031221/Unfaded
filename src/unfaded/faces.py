"""Face restoration with GFPGAN, with a strength per face.

Faces are found with YuNet (five landmarks), aligned to the 512 pixel
template GFPGAN was trained on, restored, mixed with the original crop by the
requested strength and pasted back through a feathered mask.
"""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np
import torch

from . import models
from .runtime import pick_device
from .vendor.gfpgan.gfpganv1_clean_arch import GFPGANv1Clean

TEMPLATE = np.array(
    [
        [192.98138, 239.94708],
        [318.90277, 240.1936],
        [256.63416, 314.01935],
        [201.26117, 371.41043],
        [313.08905, 371.15118],
    ],
    dtype=np.float32,
)
SIZE = 512
DETECT_SIDE = 1600
MIN_SCORE = 0.6


@dataclass
class Face:
    box: tuple[int, int, int, int]
    landmarks: np.ndarray
    score: float

    def to_json(self) -> dict:
        x, y, w, h = self.box
        return {"box": [x, y, w, h], "score": round(self.score, 3)}


def _feather() -> np.ndarray:
    mask = np.zeros((SIZE, SIZE), np.float32)
    cv2.ellipse(mask, (256, 276), (196, 224), 0, 0, 360, 1.0, -1)
    return cv2.GaussianBlur(mask, (0, 0), 22)


class FaceRestorer:
    def __init__(self, device: str = "auto") -> None:
        self.device = pick_device(device)
        self.detector = cv2.FaceDetectorYN.create(
            str(models.ensure("face_detect")), "", (320, 320), MIN_SCORE, 0.3, 5000
        )
        net = GFPGANv1Clean(
            out_size=SIZE,
            num_style_feat=512,
            channel_multiplier=2,
            decoder_load_path=None,
            fix_decoder=False,
            num_mlp=8,
            input_is_latent=True,
            different_w=True,
            narrow=1,
            sft_half=True,
        )
        state = torch.load(models.ensure("faces"), map_location="cpu", weights_only=True)
        net.load_state_dict(state["params_ema"], strict=True)
        self.net = net.to(self.device).eval()
        self.feather = _feather()

    def detect(self, rgb: np.ndarray) -> list[Face]:
        h, w = rgb.shape[:2]
        scale = DETECT_SIDE / max(h, w)
        scale = min(scale, 2.0)
        small = cv2.resize(
            rgb, (round(w * scale), round(h * scale)), interpolation=cv2.INTER_AREA if scale < 1 else cv2.INTER_CUBIC
        )
        self.detector.setInputSize((small.shape[1], small.shape[0]))
        _, found = self.detector.detect(cv2.cvtColor(small, cv2.COLOR_RGB2BGR))
        faces = []
        for row in found if found is not None else []:
            x, y, bw, bh = (row[:4] / scale).tolist()
            marks = (row[4:14].reshape(5, 2) / scale).astype(np.float32)
            faces.append(Face((round(x), round(y), round(bw), round(bh)), marks, float(row[14])))
        faces.sort(key=lambda f: f.box[0])
        return faces

    @torch.inference_mode()
    def _enhance(self, crop: np.ndarray) -> np.ndarray:
        x = torch.from_numpy(crop).permute(2, 0, 1)[None].float().div(127.5).sub(1).to(self.device)
        out = self.net(x, return_rgb=False)[0]
        out = out[0].clamp(-1, 1).add(1).mul(127.5).permute(1, 2, 0).byte().cpu().numpy()
        return out

    def restore(
        self, rgb: np.ndarray, faces: list[Face], strengths: list[float], keep_gray: bool
    ) -> tuple[np.ndarray, np.ndarray]:
        """Return the restored image and a float map (0 to 1) of where faces were replaced."""
        result = rgb.astype(np.float32)
        weight_map = np.zeros(rgb.shape[:2], np.float32)
        h, w = rgb.shape[:2]
        for face, strength in zip(faces, strengths, strict=False):
            if strength <= 0:
                continue
            matrix, _ = cv2.estimateAffinePartial2D(face.landmarks, TEMPLATE, method=cv2.LMEDS)
            if matrix is None:
                continue
            crop = cv2.warpAffine(rgb, matrix, (SIZE, SIZE), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT101)
            fixed = self._enhance(crop)
            if keep_gray:
                lum = cv2.cvtColor(fixed, cv2.COLOR_RGB2GRAY)
                fixed = np.repeat(lum[..., None], 3, axis=2)
            mixed = fixed.astype(np.float32) * strength + crop.astype(np.float32) * (1 - strength)
            inverse = cv2.invertAffineTransform(matrix)
            back = cv2.warpAffine(mixed, inverse, (w, h), flags=cv2.INTER_LINEAR)
            alpha = cv2.warpAffine(self.feather, inverse, (w, h), flags=cv2.INTER_LINEAR)
            result = result * (1 - alpha[..., None]) + back * alpha[..., None]
            weight_map = np.maximum(weight_map, alpha * strength)
        return np.clip(result, 0, 255).astype(np.uint8), weight_map

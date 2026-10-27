"""The restoration pipeline: split, tone, repair, faces, colour, upscale.

Every step returns the new image together with a change map, so the caller can
show exactly what the step did. Results of each step are memoised on the input
pixels and the step settings, which makes moving a slider re-run only the
steps downstream of it.
"""

from __future__ import annotations

import hashlib
import json
import time
from collections import OrderedDict
from collections.abc import Callable
from dataclasses import dataclass, field, replace

import numpy as np

from . import changes, fade, imaging, split
from .split import Quad

ALL_STEPS = ("split", "fade", "repair", "faces", "color", "upscale")
DEFAULT_STEPS = ("split", "fade", "repair", "faces")
MAX_MASK_FRACTION = 0.15
CACHE_BYTES = 2 * 1024**3  # step results kept for the sliders, by memory and not only by count
MAX_OUTPUT_PIXELS = 120_000_000
TONE_RANGE_LIMIT = 0.8

Progress = Callable[[str, int, str], None]


@dataclass(frozen=True)
class Options:
    steps: tuple[str, ...] = DEFAULT_STEPS
    face_strength: int = 35
    face_strengths: dict[int, list[int]] = field(default_factory=dict)
    color_strength: int = 100
    scale: int = 1
    device: str = "auto"
    quads: list[Quad] | None = None
    quarter_turns: dict[int, int] = field(default_factory=dict)
    masks: dict[int, np.ndarray] = field(default_factory=dict)
    force_fade: bool = False

    def validate(self) -> None:
        unknown = set(self.steps) - set(ALL_STEPS)
        if unknown:
            raise ValueError(f"unknown steps: {sorted(unknown)}")
        if not 0 <= self.face_strength <= 100 or not 0 <= self.color_strength <= 100:
            raise ValueError("strengths are percentages between 0 and 100")
        if self.scale not in (1, 2, 4):
            raise ValueError("scale must be 1, 2 or 4")


@dataclass
class StepResult:
    name: str
    model: str
    params: dict
    seconds: float
    image: np.ndarray
    change: np.ndarray | None
    invented: np.ndarray | None = None
    note: str = ""
    code: str = ""
    skipped: bool = False
    detail: dict = field(default_factory=dict)

    @property
    def changed_percent(self) -> float:
        return round(100 * changes.changed_fraction(self.change), 2) if self.change is not None else 0.0

    def summary(self) -> dict:
        return {
            "name": self.name,
            "model": self.model,
            "params": self.params,
            "seconds": round(self.seconds, 2),
            "changed_percent": self.changed_percent,
            "note": self.note,
            "code": self.code,
            "detail": self.detail,
            "skipped": self.skipped,
        }


@dataclass
class PhotoResult:
    index: int
    quad: Quad | None
    original: np.ndarray
    steps: list[StepResult]
    damage_mask: np.ndarray | None = None
    faces: list[dict] = field(default_factory=list)

    @property
    def final(self) -> np.ndarray:
        return self.steps[-1].image if self.steps else self.original


@dataclass
class RunResult:
    source: np.ndarray
    quads: list[Quad]
    photos: list[PhotoResult]
    options: Options
    seconds: float
    split_note: str = ""


def _digest(*parts) -> str:
    h = hashlib.blake2b(digest_size=12)
    for part in parts:
        if isinstance(part, np.ndarray):
            h.update(str(part.shape).encode())
            h.update(np.ascontiguousarray(part).tobytes())
        else:
            h.update(json.dumps(part, sort_keys=True, default=str).encode())
    return h.hexdigest()


def _nbytes(value: object) -> int:
    """Memory held by the arrays inside a cached result, so one 120 megapixel enlargement cannot fill the RAM."""
    if isinstance(value, np.ndarray):
        return value.nbytes
    if isinstance(value, (tuple, list)):
        return sum(map(_nbytes, value))
    return 1024


class Pipeline:
    def __init__(self, device: str = "auto", cache_size: int = 48, cache_bytes: int = CACHE_BYTES) -> None:
        self.device = device
        self._models: dict[str, object] = {}
        self._cache: OrderedDict[str, object] = OrderedDict()
        self._cache_size = cache_size
        self._cache_bytes = cache_bytes

    def _model(self, name: str):
        if name not in self._models:
            if name == "scratch":
                from .scratch import ScratchDetector as cls
            elif name == "inpaint":
                from .inpaint import Inpainter as cls
            elif name == "faces":
                from .faces import FaceRestorer as cls
            elif name == "color":
                from .colorize import Colorizer as cls
            elif name == "upscale":
                from .upscale import Upscaler as cls
            else:
                raise KeyError(name)
            self._models[name] = cls(self.device)
        return self._models[name]

    def _memo(self, key: str, make: Callable[[], object]):
        if key in self._cache:
            self._cache.move_to_end(key)
            return self._cache[key]
        value = make()
        self._cache[key] = value
        while len(self._cache) > 1 and (
            len(self._cache) > self._cache_size or sum(map(_nbytes, self._cache.values())) > self._cache_bytes
        ):
            self._cache.popitem(last=False)
        return value

    def detect_quads(self, source: np.ndarray) -> tuple[list[Quad], str]:
        quads = split.detect(source)
        if not quads:
            return [], "no print outline found, the whole image is used"
        if len(quads) == 1 and split.covers_whole_image(quads[0], source.shape):
            return [], "the image is a single print, nothing to cut"
        return quads, f"{len(quads)} prints found"

    def run(self, source: np.ndarray, options: Options | None = None, progress: Progress | None = None) -> RunResult:
        options = options or Options()
        options.validate()
        started = time.perf_counter()
        quads, note = [], ""
        crops: list[tuple[Quad | None, np.ndarray]] = []
        if "split" in options.steps:
            quads = options.quads if options.quads is not None else self.detect_quads(source)[0]
            note = f"{len(quads)} prints" if quads else "single image"
            for quad in quads:
                crops.append((quad, split.warp(source, quad)))
        if not crops:
            crops.append((None, source))
        photos = []
        for index, (quad, crop) in enumerate(crops):
            turns = options.quarter_turns.get(index, 0)
            if turns:
                crop = split.rotate_quarter(crop, turns)
            photos.append(self.run_photo(index, quad, crop, options, progress))
        return RunResult(source, quads, photos, options, time.perf_counter() - started, note)

    def run_photo(
        self, index: int, quad: Quad | None, crop: np.ndarray, options: Options, progress: Progress | None = None
    ) -> PhotoResult:
        photo = PhotoResult(index, quad, crop, [])
        gray = imaging.is_grayscale(crop)
        current = crop

        def announce(step: str, state: str) -> None:
            if progress:
                progress(step, index, state)

        for name in ("fade", "repair", "faces", "color", "upscale"):
            if name not in options.steps:
                continue
            announce(name, "start")
            began = time.perf_counter()
            step = getattr(self, f"_step_{name}")(current, options, index, gray, photo)
            step.seconds = time.perf_counter() - began
            photo.steps.append(step)
            current = step.image
            announce(name, "done")
        return photo

    def _step_fade(self, img, options, index, gray, photo) -> StepResult:
        lum = img.mean(axis=2)
        lo, hi = np.percentile(lum, [0.4, 99.6])
        used = float(hi - lo) / 255.0
        if used >= TONE_RANGE_LIMIT and not options.force_fade:
            return StepResult(
                "fade",
                "levels and cast removal",
                {"tone_range": round(used, 2)},
                0,
                img,
                None,
                note=f"skipped, the print already uses {used:.0%} of the tonal range",
                code="skip.tone",
                detail={"used": round(100 * used)},
                skipped=True,
            )
        out = fade.recover(img, gray)
        return StepResult(
            "fade",
            "levels and cast removal",
            {"tone_range": round(used, 2)},
            0,
            out,
            changes.change_mask(img, out),
            note=f"tonal range was {used:.0%}",
            code="info.tone",
            detail={"used": round(100 * used)},
        )

    def _step_repair(self, img, options, index, gray, photo) -> StepResult:
        override = options.masks.get(index)
        if override is not None and override.shape[:2] == img.shape[:2]:
            mask, note, code = override, "damage mask edited by hand", "info.hand_mask"
        else:
            from .scratch import probability_to_mask

            prob = self._memo(_digest("prob", img), lambda: self._model("scratch").detect(img))
            mask, note, code = probability_to_mask(prob), "", ""
        photo.damage_mask = mask
        fraction = float((mask > 127).mean())
        if fraction > MAX_MASK_FRACTION:
            return StepResult(
                "repair",
                "scratch detector + LaMa",
                {"mask_percent": round(100 * fraction, 2)},
                0,
                img,
                None,
                note="skipped, the damage mask covers too much of the print to be trusted",
                code="skip.mask_large",
                detail={"percent": round(100 * fraction)},
                skipped=True,
            )
        if fraction == 0:
            return StepResult(
                "repair",
                "scratch detector + LaMa",
                {"mask_percent": 0},
                0,
                img,
                None,
                note="no damage found",
                code="skip.no_damage",
                skipped=True,
            )
        out = self._memo(_digest("lama", img, mask), lambda: self._model("inpaint")(img, mask))
        return StepResult(
            "repair",
            "scratch detector + LaMa",
            {"mask_percent": round(100 * fraction, 2)},
            0,
            out,
            changes.change_mask(img, out),
            invented=(mask > 127).astype(np.float32),
            note=note,
            code=code,
        )

    def _step_faces(self, img, options, index, gray, photo) -> StepResult:
        restorer = self._model("faces")
        faces = self._memo(_digest("faces-found", img), lambda: restorer.detect(img))
        photo.faces = [f.to_json() for f in faces]
        if not faces:
            return StepResult(
                "faces",
                "GFPGAN v1.4",
                {"faces": 0},
                0,
                img,
                None,
                note="no faces found",
                code="skip.no_faces",
                skipped=True,
            )
        given = options.face_strengths.get(index, [])
        strengths = [given[i] if i < len(given) else options.face_strength for i in range(len(faces))]
        for entry, value in zip(photo.faces, strengths, strict=True):
            entry["strength"] = value
        key = _digest("faces", img, strengths)
        out, weight = self._memo(key, lambda: restorer.restore(img, faces, [s / 100 for s in strengths], gray))
        return StepResult(
            "faces",
            "GFPGAN v1.4",
            {"faces": len(faces), "strengths": strengths},
            0,
            out,
            changes.change_mask(img, out),
            invented=weight,
        )

    def _step_color(self, img, options, index, gray, photo) -> StepResult:
        if not gray:
            return StepResult(
                "color",
                "DDColor",
                {},
                0,
                img,
                None,
                note="skipped, the print already has colour",
                code="skip.has_color",
                skipped=True,
            )
        strength = options.color_strength / 100
        out = self._memo(_digest("color", img, strength), lambda: self._model("color")(img, strength))
        return StepResult(
            "color",
            "DDColor",
            {"strength": options.color_strength},
            0,
            out,
            changes.change_mask(img, out),
            invented=np.full(img.shape[:2], strength, np.float32),
            note="colours are the model's guess",
            code="info.color_guess",
        )

    def _step_upscale(self, img, options, index, gray, photo) -> StepResult:
        scale = options.scale
        if scale == 1:
            return StepResult(
                "upscale", "Real-ESRGAN x4", {"scale": 1}, 0, img, None, note="skipped", code="skip.off", skipped=True
            )
        while scale > 1 and img.shape[0] * img.shape[1] * scale * scale > MAX_OUTPUT_PIXELS:
            scale //= 2
        if scale == 1:
            return StepResult(
                "upscale",
                "Real-ESRGAN x4",
                {"scale": 1},
                0,
                img,
                None,
                note="skipped, the print is already very large",
                code="skip.large",
                skipped=True,
            )
        out = self._memo(_digest("up", img, scale), lambda: self._model("upscale")(img, scale))
        note = "" if scale == options.scale else f"scale reduced to {scale} to keep the file manageable"
        code = "" if scale == options.scale else "info.scale_reduced"
        return StepResult(
            "upscale",
            "Real-ESRGAN x4",
            {"scale": scale},
            0,
            out,
            changes.change_mask(img, out),
            note=note,
            code=code,
            detail={"scale": scale},
        )


def with_steps(options: Options, **kwargs) -> Options:
    return replace(options, **kwargs)

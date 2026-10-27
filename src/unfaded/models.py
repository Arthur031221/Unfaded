"""Model registry, download and verification.

Weights are not part of the package. They are fetched once into the cache
directory and checked against a pinned SHA-256. Plain checkpoints are loaded with
``weights_only=True``. The LaMa file is TorchScript, which can hold code, so the
checksum is the only protection for it and it is verified before every first use.
"""

from __future__ import annotations

import hashlib
import os
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ModelSpec:
    key: str
    filename: str
    url: str
    sha256: str
    size: int
    purpose: str
    license: str
    source: str


REGISTRY: dict[str, ModelSpec] = {
    spec.key: spec
    for spec in (
        ModelSpec(
            "scratch",
            "bopbtl_scratch_detector.pt",
            "https://huggingface.co/databuzzword/bringing-old-photos-back-to-life/resolve/main/"
            "Global/checkpoints/detection/FT_Epoch_latest.pt",
            "b2d7ab04e9b3885c6b1991bb7a0b823129dd6e3ac078a9fd059ebd2a7ba59a95",
            451_663_663,
            "scratch and crease detection",
            "MIT",
            "microsoft/Bringing-Old-Photos-Back-to-Life",
        ),
        ModelSpec(
            "inpaint",
            "big-lama.pt",
            "https://github.com/enesmsahin/simple-lama-inpainting/releases/download/v0.1.0/big-lama.pt",
            "7ba7aa7ac37a4d41fdbbeba3a2af7ead18058552997e3a3cd1a3b2210c9e6b4c",
            205_803_670,
            "inpainting of the damage mask",
            "Apache-2.0",
            "advimman/lama (TorchScript export)",
        ),
        ModelSpec(
            "face_detect",
            "face_detection_yunet_2023mar.onnx",
            "https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/"
            "face_detection_yunet_2023mar.onnx",
            "8f2383e4dd3cfbb4553ea8718107fc0423210dc964f9f4280604804ed2552fa4",
            232_589,
            "face detection with five landmarks",
            "MIT",
            "opencv/opencv_zoo",
        ),
        ModelSpec(
            "faces",
            "GFPGANv1.4.pth",
            "https://github.com/TencentARC/GFPGAN/releases/download/v1.3.0/GFPGANv1.4.pth",
            "e2cd4703ab14f4d01fd1383a8a8b266f9a5833dacee8e6a79d3bf21a1b6be5ad",
            348_632_874,
            "face restoration",
            "Apache-2.0",
            "TencentARC/GFPGAN",
        ),
        ModelSpec(
            "color",
            "ddcolor_paper_tiny.pth",
            "https://huggingface.co/piddnad/DDColor-models/resolve/main/ddcolor_paper_tiny.pth",
            "81dd643904f4664c3718513e3320ae3db0c567f0d3e18398606659adee7bfc17",
            220_393_145,
            "colorization",
            "Apache-2.0",
            "piddnad/DDColor",
        ),
        ModelSpec(
            "upscale",
            "RealESRGAN_x4plus.pth",
            "https://github.com/xinntao/Real-ESRGAN/releases/download/v0.1.0/RealESRGAN_x4plus.pth",
            "4fa0d38905f75ac06eb49a7951b426670021be3018265fd191d2125df9d682f1",
            67_040_989,
            "4x upscaling",
            "BSD-3-Clause",
            "xinntao/Real-ESRGAN",
        ),
    )
}

STEP_MODELS: dict[str, tuple[str, ...]] = {
    "repair": ("scratch", "inpaint"),
    "faces": ("face_detect", "faces"),
    "color": ("color",),
    "upscale": ("upscale",),
}

Progress = Callable[[int, int], None]


def cache_dir() -> Path:
    root = os.environ.get("UNFADED_HOME")
    base = Path(root) if root else Path.home() / ".cache" / "unfaded"
    return base / "models"


def model_path(key: str) -> Path:
    return cache_dir() / REGISTRY[key].filename


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def is_installed(key: str) -> bool:
    path = model_path(key)
    return path.is_file() and path.stat().st_size == REGISTRY[key].size


def _verified(key: str) -> bool:
    """Hash a cached file once and remember the result for as long as size and mtime stay the same."""
    path = model_path(key)
    stat = path.stat()
    stamp = f"{REGISTRY[key].sha256}:{stat.st_size}:{stat.st_mtime_ns}"
    marker = path.with_name(path.name + ".ok")
    if marker.is_file() and marker.read_text() == stamp:
        return True
    if sha256_of(path) != REGISTRY[key].sha256:
        return False
    marker.write_text(stamp)
    return True


def ensure(key: str, progress: Progress | None = None) -> Path:
    """Return the verified local path of a model, downloading it when absent."""
    spec = REGISTRY[key]
    path = model_path(key)
    if is_installed(key):
        if not _verified(key):
            raise RuntimeError(f"{spec.filename}: checksum mismatch, delete the file from {path.parent} and retry")
        return path
    path.parent.mkdir(parents=True, exist_ok=True)
    part = path.with_suffix(path.suffix + ".part")
    request = urllib.request.Request(spec.url, headers={"User-Agent": "unfaded"})
    digest = hashlib.sha256()
    done = 0
    with urllib.request.urlopen(request, timeout=60) as response, part.open("wb") as out:
        while block := response.read(1 << 20):
            out.write(block)
            digest.update(block)
            done += len(block)
            if progress:
                progress(done, spec.size)
    if digest.hexdigest() != spec.sha256:
        part.unlink(missing_ok=True)
        raise RuntimeError(f"{spec.filename}: checksum mismatch, the download was discarded")
    part.replace(path)
    return path


def ensure_for_steps(steps: set[str], progress: Progress | None = None) -> None:
    for step in steps:
        for key in STEP_MODELS.get(step, ()):
            ensure(key, progress)


def status() -> list[dict]:
    return [
        {
            "key": spec.key,
            "file": spec.filename,
            "purpose": spec.purpose,
            "license": spec.license,
            "source": spec.source,
            "size_mb": round(spec.size / 1e6, 1),
            "installed": is_installed(spec.key),
        }
        for spec in REGISTRY.values()
    ]

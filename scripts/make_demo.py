"""Render the files the GitHub Pages demo reads. Needs the model weights and takes a few minutes on a GPU.

The inputs are public domain scans from examples/photos with synthetic damage drawn on top, so the
damage is known and the page can be rebuilt with the same seeds.

    python scripts/make_demo.py            # writes demo/ and examples/scans/
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

import numpy as np

from unfaded import __version__, changes, imaging, models, runtime, synth
from unfaded.pipeline import ALL_STEPS, Options, Pipeline

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "demo"
PHOTOS = ROOT / "examples" / "photos"
SIDE = 1500

EXAMPLES = [
    {
        "id": "album",
        "name": "Four prints on one scan",
        "files": [
            "roy-family-1891.jpg",
            "king-family.jpg",
            "clemons-logging-camp-1926.jpg",
            "knowles-family-portrait.jpg",
        ],
        "damage": True,
        "scan": (2400, 1800),
    },
    {"id": "creased", "name": "Creased family portrait", "files": ["roy-family-1891.jpg"], "damage": True},
    {"id": "camp", "name": "Scratched group photo", "files": ["clemons-logging-camp-1926.jpg"], "damage": True},
]


def jpeg(path: Path, rgb: np.ndarray, side: int = SIDE, quality: int = 82) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    imaging.save(path, imaging.fit_long_side(rgb, side) if max(rgb.shape[:2]) > side else rgb, quality)
    return path.relative_to(OUT).as_posix()


def build_input(spec: dict) -> tuple[np.ndarray, list[np.ndarray]]:
    prints = []
    for i, name in enumerate(spec["files"]):
        rgb = imaging.fit_long_side(imaging.load_rgb(PHOTOS / name), 1100)
        if spec["damage"]:
            rgb, _ = synth.add_damage(rgb, seed=11 + i, scratches=10, creases=1, dust=90)
        prints.append(rgb)
    if len(prints) == 1:
        return prints[0], []
    scan, truth = synth.compose_scan(prints, size=spec["scan"], seed=4)
    return scan, truth


def main() -> None:
    device = "auto"
    models.ensure_for_steps(ALL_STEPS)
    pipe = Pipeline(device)
    if OUT.exists():
        shutil.rmtree(OUT)
    index = {
        "version": __version__,
        "device": runtime.describe(runtime.pick_device(device)),
        "steps": list(ALL_STEPS),
        "examples": [],
    }
    for spec in EXAMPLES:
        print("rendering", spec["id"], flush=True)
        source, _ = build_input(spec)
        (ROOT / "examples" / "scans").mkdir(parents=True, exist_ok=True)
        imaging.save(ROOT / "examples" / "scans" / f"{spec['id']}-damaged.jpg", source, 92)
        base = Options(steps=ALL_STEPS, face_strength=35, scale=2)
        result = pipe.run(source, base)
        strong = pipe.run(source, Options(steps=ALL_STEPS[: ALL_STEPS.index("faces") + 1], face_strength=100))
        quads = pipe.detect_quads(source)[0] if len(spec["files"]) > 1 else []
        folder = OUT / spec["id"]
        entry = {
            "id": spec["id"],
            "name": spec["name"],
            "width": int(source.shape[1]),
            "height": int(source.shape[0]),
            "quads": [q.to_json() for q in quads],
            "note": result.split_note,
            "seconds": round(result.seconds, 2),
            "source": jpeg(folder / "source.jpg", source),
            "thumb": jpeg(folder / "thumb.jpg", source, 360, 78),
            "photos": [],
        }
        for photo, hard in zip(result.photos, strong.photos, strict=True):
            tag = f"p{photo.index}"
            item = {
                "width": int(photo.final.shape[1]),
                "height": int(photo.final.shape[0]),
                "original": [int(photo.original.shape[1]), int(photo.original.shape[0])],
                "faces": photo.faces,
                "steps": [],
            }
            item["original_url"] = jpeg(folder / tag / "original.jpg", photo.original)
            for step in photo.steps:
                row = step.summary() | {
                    "invented": step.invented is not None or (step.name == "upscale" and not step.skipped)
                }
                row["image"] = jpeg(folder / tag / f"{step.name}.jpg", step.image)
                change = step.change if step.change is not None else np.zeros(step.image.shape[:2], np.float32)
                row["heat"] = jpeg(folder / tag / f"{step.name}-heat.jpg", changes.heat_overlay(step.image, change))
                weight = step.invented
                if weight is None:
                    weight = (
                        np.ones(step.image.shape[:2], np.float32)
                        if step.name == "upscale" and not step.skipped
                        else np.zeros(step.image.shape[:2], np.float32)
                    )
                row["inv"] = jpeg(
                    folder / tag / f"{step.name}-inv.jpg", changes.heat_overlay(step.image, np.clip(weight, 0, 1))
                )
                item["steps"].append(row)
            strong_faces = next(s for s in hard.steps if s.name == "faces")
            if photo.faces:
                item["faces_full"] = jpeg(folder / tag / "faces-full.jpg", strong_faces.image)
            if photo.damage_mask is not None:
                path = folder / tag / "mask.png"
                path.write_bytes(changes.mask_to_png_bytes(photo.damage_mask))
                item["mask"] = path.relative_to(OUT).as_posix()
            entry["photos"].append(item)
        index["examples"].append(entry)
    (OUT / "index.json").write_text(json.dumps(index, separators=(",", ":")))
    total = sum(f.stat().st_size for f in OUT.rglob("*") if f.is_file())
    print(f"wrote {OUT} ({total / 1e6:.1f} MB)")


if __name__ == "__main__":
    sys.exit(main())

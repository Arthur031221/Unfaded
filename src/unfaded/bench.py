"""Benchmark: repair quality on synthetic damage, print splitting accuracy and time per step.

The clean reference is a scan that already carries its own wear. Known damage is added on top with a fixed
seed, so every number can be reproduced with ``unfaded bench``.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import cv2
import numpy as np

from . import imaging, models, runtime, split, synth
from .pipeline import Options, Pipeline

SSIM_C1, SSIM_C2 = (0.01 * 255) ** 2, (0.03 * 255) ** 2


CPU_SIDE = 600  # the CPU leg is far slower, so it times a smaller image


def psnr(a: np.ndarray, b: np.ndarray, where: np.ndarray | None = None) -> float:
    diff = (a.astype(np.float64) - b.astype(np.float64)) ** 2
    if where is not None:
        diff = diff[where > 0]
    mse = float(diff.mean())
    return 99.0 if mse == 0 else 10 * np.log10(255.0**2 / mse)


def ssim(a: np.ndarray, b: np.ndarray) -> float:
    """Mean SSIM over the grey image with an 11 by 11 Gaussian window, the usual definition."""
    x = cv2.cvtColor(a, cv2.COLOR_RGB2GRAY).astype(np.float64)
    y = cv2.cvtColor(b, cv2.COLOR_RGB2GRAY).astype(np.float64)
    blur = lambda m: cv2.GaussianBlur(m, (11, 11), 1.5)  # noqa: E731
    mx, my = blur(x), blur(y)
    sxx, syy, sxy = blur(x * x) - mx * mx, blur(y * y) - my * my, blur(x * y) - mx * my
    score = ((2 * mx * my + SSIM_C1) * (2 * sxy + SSIM_C2)) / ((mx * mx + my * my + SSIM_C1) * (sxx + syy + SSIM_C2))
    return float(score.mean())


def quad_iou(points: np.ndarray, truth: np.ndarray, shape: tuple[int, int]) -> float:
    a = np.zeros(shape, np.uint8)
    b = np.zeros(shape, np.uint8)
    cv2.fillPoly(a, [points.astype(np.int32)], 1)
    cv2.fillPoly(b, [truth.astype(np.int32)], 1)
    union = int(np.logical_or(a, b).sum())
    return float(np.logical_and(a, b).sum()) / max(union, 1)


def default_images() -> list[Path]:
    here = Path(__file__).resolve()
    for root in (here.parents[2] / "examples" / "photos", Path.cwd() / "examples" / "photos"):
        if root.is_dir():
            return sorted(root.glob("*.jpg"))
    raise SystemExit("unfaded bench: pass image paths, the bundled examples were not found")


def repair_quality(pipe: Pipeline, images: list[Path], seed: int) -> dict:
    rows = []
    for path in images:
        clean = imaging.load_rgb(path)
        clean = imaging.fit_long_side(clean, 1600)
        damaged, truth = synth.add_damage(clean, seed=seed)
        run = pipe.run(damaged, Options(steps=("repair",), scale=1))
        out = run.photos[0].final
        rows.append(
            {
                "image": path.name,
                "psnr_damaged": psnr(clean, damaged),
                "psnr_repaired": psnr(clean, out),
                "psnr_damaged_region": psnr(clean, damaged, truth),
                "psnr_repaired_region": psnr(clean, out, truth),
                "ssim_damaged": ssim(clean, damaged),
                "ssim_repaired": ssim(clean, out),
                "mask_percent": run.photos[0].steps[0].params.get("mask_percent"),
            }
        )
    mean = lambda key: float(np.mean([r[key] for r in rows]))  # noqa: E731
    return {"rows": rows, **{f"mean_{k}": mean(k) for k in rows[0] if k not in ("image", "mask_percent")}}


def split_accuracy(images: list[Path], seed: int, backgrounds=((246, 246, 244), (20, 20, 22), (190, 190, 185))) -> dict:
    ious, found, expected = [], 0, 0
    prints = [imaging.fit_long_side(imaging.load_rgb(p), 900) for p in images]
    for index, bg in enumerate(backgrounds):
        scan, truth = synth.compose_scan(prints, background=bg, seed=seed + index)
        quads = split.detect(scan)
        expected += len(truth)
        found += len(quads)
        for corners in truth:
            best = max((quad_iou(q.as_array(), corners, scan.shape[:2]) for q in quads), default=0.0)
            ious.append(best)
    return {
        "scans": len(backgrounds),
        "prints_per_scan": len(prints),
        "expected": expected,
        "found": found,
        "mean_iou": float(np.mean(ious)),
        "min_iou": float(np.min(ious)),
    }


def step_timing(images: list[Path], device: str, side: int = 1200) -> dict:
    pipe = Pipeline(device)
    loaded = [(imaging.load_rgb(p), p) for p in images]
    rgb, path = max(loaded, key=lambda item: max(item[0].shape[:2]))
    rgb = imaging.fit_long_side(rgb, side)
    steps = ("fade", "repair", "faces", "color", "upscale")
    options = Options(steps=steps, scale=2, force_fade=True, device=device)
    pipe.run(rgb, options)  # warm up so model loading is not counted
    pipe._cache.clear()
    run = pipe.run(rgb, options)
    return {
        "image": path.name,
        "device": runtime.describe(runtime.pick_device(device)),
        "size": [rgb.shape[1], rgb.shape[0]],
        "seconds": {s.name: round(s.seconds, 2) for s in run.photos[0].steps},
        "total": round(run.seconds, 2),
    }


def run_benchmark(args) -> int:
    images = [Path(p) for p in args.images] or default_images()
    models.ensure_for_steps({"repair", "faces", "color", "upscale"})
    pipe = Pipeline(args.device)
    began = time.perf_counter()
    quality = repair_quality(pipe, images, args.seed)
    splitting = split_accuracy(images, args.seed)
    timing = {args.device: step_timing(images, args.device)}
    if args.cpu and args.device != "cpu":
        timing["cpu"] = step_timing(images, "cpu", CPU_SIDE)
    report = {
        "seed": args.seed,
        "images": [p.name for p in images],
        "repair": quality,
        "split": splitting,
        "timing": timing,
        "wall_seconds": round(time.perf_counter() - began, 1),
    }

    print(f"repair, seed {args.seed}, {len(images)} images, damage added to the scan then repaired")
    print(
        f"  {'image':34s} {'PSNR before':>11s} {'after':>7s}   {'region before':>13s} {'after':>7s}   SSIM before/after"
    )
    for r in quality["rows"]:
        print(
            f"  {r['image']:34s} {r['psnr_damaged']:11.2f} {r['psnr_repaired']:7.2f}   "
            f"{r['psnr_damaged_region']:13.2f} {r['psnr_repaired_region']:7.2f}   "
            f"{r['ssim_damaged']:.3f} / {r['ssim_repaired']:.3f}"
        )
    print(
        f"  mean PSNR {quality['mean_psnr_damaged']:.2f} -> {quality['mean_psnr_repaired']:.2f} dB "
        f"(gain {quality['mean_psnr_repaired'] - quality['mean_psnr_damaged']:+.2f}), "
        f"mean SSIM {quality['mean_ssim_damaged']:.3f} -> {quality['mean_ssim_repaired']:.3f}"
    )
    print(
        f"split, {splitting['scans']} scans with {splitting['prints_per_scan']} prints each: "
        f"found {splitting['found']} of {splitting['expected']}, mean IoU {splitting['mean_iou']:.3f}, "
        f"worst {splitting['min_iou']:.3f}"
    )
    for t in timing.values():
        steps = ", ".join(f"{k} {v}s" for k, v in t["seconds"].items())
        print(f"time per step on {t['device']}, {t['size'][0]}x{t['size'][1]} px: {steps}, total {t['total']}s")
    if args.json_path:
        Path(args.json_path).write_text(json.dumps(report, indent=2))
    return 0

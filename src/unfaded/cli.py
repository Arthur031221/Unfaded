"""Command line entry point: restore, split, serve, models, bench."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__

IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".bmp", ".webp"}


def _expand(paths: list[str]) -> list[Path]:
    found: list[Path] = []
    for raw in paths:
        p = Path(raw)
        if p.is_dir():
            found += sorted(f for f in p.iterdir() if f.suffix.lower() in IMAGE_SUFFIXES and ".unfaded" not in f.name)
        elif p.is_file():
            found.append(p)
        else:
            raise SystemExit(f"unfaded: no such file or folder: {raw}")
    if not found:
        raise SystemExit("unfaded: no images to process")
    return found


def _download_progress(done: int, total: int) -> None:
    print(f"\rdownloading model weights {100 * done // max(total, 1):3d}%", end="", file=sys.stderr, flush=True)
    if done >= total:
        print(file=sys.stderr)


def _steps(args: argparse.Namespace) -> tuple[str, ...]:
    from .pipeline import ALL_STEPS, DEFAULT_STEPS

    chosen = set(DEFAULT_STEPS)
    for name in args.enable or []:
        chosen.add(name)
    for name in args.skip or []:
        chosen.discard(name)
    if args.colorize:
        chosen.add("color")
    if args.scale and args.scale > 1:
        chosen.add("upscale")
    return tuple(s for s in ALL_STEPS if s in chosen)


def _options(args: argparse.Namespace):
    from .pipeline import Options

    steps = _steps(args)
    options = Options(
        steps=steps,
        face_strength=args.face_strength,
        color_strength=args.color_strength,
        scale=args.scale or (2 if "upscale" in steps else 1),
        force_fade=args.force_fade,
    )
    options.validate()
    return options


def _output_path(source: Path, out_dir: Path | None, fmt: str, number: int | None) -> Path:
    stem = f"{source.stem}.unfaded" + (f"-{number}" if number is not None else "")
    return (out_dir or source.parent) / f"{stem}.{fmt}"


def cmd_restore(args: argparse.Namespace) -> int:
    from . import imaging, models, provenance
    from .pipeline import Pipeline

    files = _expand(args.inputs)
    options = _options(args)
    steps = options.steps
    models.ensure_for_steps(set(steps), progress=_download_progress)
    out_dir = Path(args.output) if args.output else None
    if out_dir:
        out_dir.mkdir(parents=True, exist_ok=True)
    pipe = Pipeline(args.device)
    for source in files:
        run = pipe.run(imaging.load_rgb(source), options)
        print(f"{source.name}: {run.split_note or 'one print'}")
        many = len(run.photos) > 1
        for photo in run.photos:
            target = _output_path(source, out_dir, args.format, photo.index + 1 if many else None)
            if target.resolve() == source.resolve():
                raise SystemExit("unfaded: refusing to overwrite the original")
            imaging.save(target, photo.final)
            provenance.write_sidecar(source, target, photo)
            print(f"  wrote {target}")
            if args.explain:
                for step in photo.steps:
                    tag = "skipped" if step.skipped else f"{step.changed_percent:5.1f}% changed"
                    note = step.note.removeprefix("skipped, ") if step.skipped else step.note
                    print(f"    {step.name:8s} {tag:>16s}  {step.seconds:5.2f}s  {note}")
    return 0


def cmd_split(args: argparse.Namespace) -> int:
    from . import imaging, split

    out_dir = Path(args.output) if args.output else None
    if out_dir:
        out_dir.mkdir(parents=True, exist_ok=True)
    for source in _expand(args.inputs):
        rgb = imaging.load_rgb(source)
        quads = split.detect(rgb)
        print(f"{source.name}: {len(quads)} prints")
        for number, quad in enumerate(quads, 1):
            target = (out_dir or source.parent) / f"{source.stem}.print-{number}.{args.format}"
            imaging.save(target, split.warp(rgb, quad))
            print(f"  wrote {target}")
    return 0


def cmd_models(args: argparse.Namespace) -> int:
    from . import models

    if args.fetch:
        models.ensure_for_steps({"repair", "faces", "color", "upscale"}, progress=_download_progress)
    for row in models.status():
        mark = "installed" if row["installed"] else "missing"
        print(f"{row['key']:12s} {mark:10s} {row['size_mb']:7.1f} MB  {row['license']:12s} {row['purpose']}")
    print(f"cache: {models.cache_dir()}")
    return 0


def cmd_serve(args: argparse.Namespace) -> int:
    import uvicorn

    from .server import create_app

    app = create_app(device=args.device)
    print(f"Unfaded is running at http://{args.host}:{args.port}")
    uvicorn.run(app, host=args.host, port=args.port, log_level="warning")
    return 0


def cmd_bench(args: argparse.Namespace) -> int:
    from .bench import run_benchmark

    return run_benchmark(args)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="unfaded", description="Restore old family photos on your own GPU.")
    parser.add_argument("--version", action="version", version=f"unfaded {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    r = sub.add_parser("restore", help="restore photos or whole folders")
    r.add_argument("inputs", nargs="+", help="image files or folders")
    r.add_argument("-o", "--output", help="output folder (default: next to each input)")
    r.add_argument("--format", choices=("jpg", "png"), default="jpg")
    r.add_argument("--face-strength", type=int, default=35, help="0 to 100, how far faces move toward the model")
    r.add_argument("--colorize", action="store_true", help="add colour to black and white prints")
    r.add_argument("--color-strength", type=int, default=100)
    r.add_argument(
        "--scale",
        type=int,
        choices=(1, 2, 4),
        default=None,
        help="upscale factor, 2 when --enable upscale is used alone",
    )
    r.add_argument("--skip", action="append", choices=("split", "fade", "repair", "faces"), help="turn a step off")
    r.add_argument("--enable", action="append", choices=("color", "upscale"), help="turn an optional step on")
    r.add_argument("--force-fade", action="store_true", help="run tone recovery even on well exposed prints")
    r.add_argument("--device", default="auto", help="auto, cuda, mps or cpu")
    r.add_argument("--explain", action="store_true", help="print what each step changed")
    r.set_defaults(func=cmd_restore)

    s = sub.add_parser("split", help="only cut a scan into separate prints")
    s.add_argument("inputs", nargs="+")
    s.add_argument("-o", "--output")
    s.add_argument("--format", choices=("jpg", "png"), default="jpg")
    s.set_defaults(func=cmd_split)

    m = sub.add_parser("models", help="show or download model weights")
    m.add_argument("--fetch", action="store_true", help="download everything now")
    m.set_defaults(func=cmd_models)

    w = sub.add_parser("serve", help="start the local web interface")
    w.add_argument("--host", default="127.0.0.1")
    w.add_argument("--port", type=int, default=8765)
    w.add_argument("--device", default="auto")
    w.set_defaults(func=cmd_serve)

    b = sub.add_parser("bench", help="measure quality on synthetic damage and time per step")
    b.add_argument("images", nargs="*", help="clean photos to damage (default: bundled examples)")
    b.add_argument("--seed", type=int, default=5)
    b.add_argument("--device", default="auto")
    b.add_argument("--cpu", action="store_true", help="also time every step on the CPU")
    b.add_argument("--json", dest="json_path", help="write results to this file")
    b.set_defaults(func=cmd_bench)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())

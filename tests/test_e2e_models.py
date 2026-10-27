"""End to end runs with the real model weights. Skipped unless the weights are in the cache."""

from __future__ import annotations

import numpy as np
import pytest

from unfaded import imaging, models, synth
from unfaded.bench import psnr
from unfaded.cli import main
from unfaded.pipeline import Options, Pipeline

pytestmark = pytest.mark.models

REQUIRED = {"repair", "faces"}


@pytest.fixture(scope="module", autouse=True)
def weights_present():
    keys = [key for step in REQUIRED for key in models.STEP_MODELS[step]]
    if all(models.is_installed(key) for key in keys):
        return
    pytest.skip("model weights are not in the cache, run `unfaded models --fetch`")


@pytest.fixture(scope="module")
def pipe():
    return Pipeline("auto")


def test_repair_improves_a_damaged_photo(pipe, example_paths):
    clean = imaging.fit_long_side(imaging.load_rgb(example_paths[1]), 900)
    damaged, _ = synth.add_damage(clean, seed=5)
    run = pipe.run(damaged, Options(steps=("repair",), scale=1))
    repaired = run.photos[0].final
    assert repaired.shape == clean.shape
    assert psnr(clean, repaired) > psnr(clean, damaged)


def test_faces_step_reports_what_it_invented(pipe, example_paths):
    img = imaging.fit_long_side(imaging.load_rgb(example_paths[1]), 900)
    run = pipe.run(img, Options(steps=("faces",), scale=1, face_strength=100))
    faces = run.photos[0].steps[-1]
    assert faces.name == "faces"
    if not faces.skipped:
        assert faces.invented is not None and faces.invented.any()
        assert faces.model


def test_cli_restores_and_writes_a_sidecar(tmp_path, capsys):
    from pathlib import Path

    scan = Path(__file__).resolve().parents[1] / "examples" / "scans" / "camp-damaged.jpg"
    assert main(["restore", str(scan), "-o", str(tmp_path), "--skip", "faces", "--explain"]) == 0
    outputs = sorted(tmp_path.glob("*.jpg"))
    assert outputs and all(p.with_name(p.name + ".xmp").exists() for p in outputs)
    assert "repair" in capsys.readouterr().out
    first = imaging.load_rgb(outputs[0])
    assert first.dtype == np.uint8 and first.ndim == 3

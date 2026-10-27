from __future__ import annotations

from pathlib import Path

import pytest

from unfaded import imaging

EXAMPLES = Path(__file__).resolve().parents[1] / "examples" / "photos"


@pytest.fixture(scope="session")
def example_paths() -> list[Path]:
    return sorted(EXAMPLES.glob("*.jpg"))


@pytest.fixture(scope="session")
def portrait(example_paths):
    return imaging.fit_long_side(imaging.load_rgb(example_paths[0]), 700)


@pytest.fixture(scope="session")
def scan(example_paths):
    from unfaded import synth

    prints = [imaging.fit_long_side(imaging.load_rgb(p), 600) for p in example_paths[:3]]
    image, truth = synth.compose_scan(prints, size=(1600, 1200), seed=2)
    return image, truth


@pytest.fixture(autouse=True)
def isolated_home(request, tmp_path, monkeypatch):
    """Keep tests away from the real model cache, except the ones that need the real weights."""
    if request.node.get_closest_marker("models"):
        return
    monkeypatch.setenv("UNFADED_HOME", str(tmp_path / "home"))

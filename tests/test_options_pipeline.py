import numpy as np
import pytest

from unfaded.pipeline import ALL_STEPS, DEFAULT_STEPS, Options, Pipeline


def test_defaults_are_valid():
    Options().validate()
    assert set(DEFAULT_STEPS) <= set(ALL_STEPS)
    assert "color" not in DEFAULT_STEPS and "upscale" not in DEFAULT_STEPS


@pytest.mark.parametrize(
    "kwargs",
    [{"steps": ("nope",)}, {"face_strength": 101}, {"color_strength": -1}, {"scale": 3}],
)
def test_invalid_options_are_rejected(kwargs):
    with pytest.raises(ValueError):
        Options(**kwargs).validate()


def test_split_and_fade_need_no_model(scan):
    image, truth = scan
    run = Pipeline("cpu").run(image, Options(steps=("split", "fade"), force_fade=True))
    assert len(run.photos) == len(truth)
    assert [s.name for s in run.photos[0].steps] == ["fade"]
    assert run.photos[0].final.dtype == np.uint8


def test_manual_quads_override_detection(scan):
    from unfaded.split import Quad

    image, _ = scan
    quad = Quad(np.array([[100, 100], [500, 100], [500, 400], [100, 400]], np.float32), 1.0)
    run = Pipeline("cpu").run(image, Options(steps=("split",), quads=[quad]))
    assert len(run.photos) == 1
    assert abs(run.photos[0].original.shape[1] - 400) < 20


def test_quarter_turns_rotate_the_crop(scan):
    image, _ = scan
    pipe = Pipeline("cpu")
    plain = pipe.run(image, Options(steps=("split",))).photos[0].original
    turned = pipe.run(image, Options(steps=("split",), quarter_turns={0: 1})).photos[0].original
    assert turned.shape[:2] == plain.shape[:2][::-1]


def test_memo_reuses_a_result_and_evicts_the_oldest():
    pipe = Pipeline("cpu", cache_size=2)
    calls = []
    for key in ("a", "a", "b", "c", "a"):
        pipe._memo(key, lambda key=key: calls.append(key) or key)
    assert calls == ["a", "b", "c", "a"]
    assert list(pipe._cache) == ["c", "a"]


def test_well_exposed_print_skips_tone_recovery(portrait):
    stretched = np.clip((portrait.astype(float) - portrait.min()) * 255 / max(np.ptp(portrait), 1), 0, 255).astype(
        np.uint8
    )
    step = Pipeline("cpu").run(stretched, Options(steps=("fade",))).photos[0].steps[0]
    assert step.skipped and step.code

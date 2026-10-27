"""The detector also finds dark scratches, by running on the inverted image."""

from __future__ import annotations

import numpy as np

from unfaded import scratch


class Stub(scratch.ScratchDetector):
    """Reacts only to bright pixels, like a network trained on light scratches."""

    def __init__(self) -> None:  # no weights needed
        pass

    def _probability(self, gray, short_side):
        return (gray > 200).astype(np.float32)


def test_dark_pixels_score_the_dark_weight():
    img = np.full((64, 64, 3), 128, np.uint8)
    img[10, :] = 255
    img[40, :] = 0
    prob = Stub().detect(img, scales=(64,))
    assert prob[10].min() == 1.0
    assert np.isclose(prob[40].min(), scratch.DARK_WEIGHT)
    assert prob[25].max() == 0.0

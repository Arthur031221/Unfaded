import xml.etree.ElementTree as ET

import numpy as np

from unfaded import provenance
from unfaded.pipeline import PhotoResult, StepResult


def make_photo(skipped=False):
    img = np.zeros((4, 4, 3), np.uint8)
    steps = [
        StepResult("fade", "levels", {"a": 1}, 0.1, img, None),
        StepResult("faces", "GFPGAN v1.4", {"strength": 35}, 0.2, img, None, skipped=skipped),
    ]
    return PhotoResult(0, None, img, steps)


def test_sidecar_names_source_hash_and_invented_steps(tmp_path):
    source = tmp_path / "scan.jpg"
    source.write_bytes(b"original bytes")
    output = tmp_path / "scan.unfaded.jpg"
    path = provenance.write_sidecar(source, output, make_photo())
    assert path.name == "scan.unfaded.jpg.xmp"
    text = path.read_text(encoding="utf-8")
    ET.fromstring(text.split("?>", 1)[1].rsplit("<?xpacket", 1)[0])  # well formed
    assert provenance.file_sha256(source) in text
    assert 'ModelGenerated="faces"' in text
    assert "GFPGAN v1.4" in text


def test_skipped_steps_are_not_reported_as_model_generated(tmp_path):
    source = tmp_path / "a.jpg"
    source.write_bytes(b"x")
    text = provenance.build_xmp(source, tmp_path / "b.jpg", make_photo(skipped=True))
    assert 'ModelGenerated="none"' in text


def test_escapes_markup_in_names(tmp_path):
    source = tmp_path / 'a"&<.jpg'
    source.write_bytes(b"x")
    text = provenance.build_xmp(source, tmp_path / "b.jpg", make_photo())
    ET.fromstring(text.split("?>", 1)[1].rsplit("<?xpacket", 1)[0])

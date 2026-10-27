import pytest

from unfaded import cli


def test_split_writes_one_file_per_print(tmp_path, scan, capsys):
    from unfaded import imaging

    path = tmp_path / "album.jpg"
    imaging.save(path, scan[0])
    assert cli.main(["split", str(path), "-o", str(tmp_path / "out")]) == 0
    assert len(list((tmp_path / "out").glob("album.print-*.jpg"))) == 3
    assert "3 prints" in capsys.readouterr().out


def test_restore_writes_copy_and_sidecar_and_leaves_the_original_alone(tmp_path, scan, capsys):
    from unfaded import imaging, provenance

    path = tmp_path / "album.jpg"
    imaging.save(path, scan[0])
    before = provenance.file_sha256(path)
    args = [
        "restore",
        str(path),
        "-o",
        str(tmp_path / "out"),
        "--skip",
        "repair",
        "--skip",
        "faces",
        "--force-fade",
        "--explain",
        "--device",
        "cpu",
    ]
    assert cli.main(args) == 0
    out = sorted((tmp_path / "out").iterdir())
    assert [p.name for p in out if p.suffix == ".jpg"] == [f"album.unfaded-{i}.jpg" for i in (1, 2, 3)]
    assert len([p for p in out if p.suffix == ".xmp"]) == 3
    assert provenance.file_sha256(path) == before
    assert "fade" in capsys.readouterr().out


def test_folders_skip_files_this_tool_wrote(tmp_path):
    for name in ("a.jpg", "a.unfaded.jpg", "a.unfaded.jpg.xmp", "notes.txt"):
        (tmp_path / name).write_bytes(b"x")
    assert [p.name for p in cli._expand([str(tmp_path)])] == ["a.jpg"]


def test_missing_input_is_a_clear_error(tmp_path):
    with pytest.raises(SystemExit, match="no such file"):
        cli.main(["split", str(tmp_path / "nope.jpg")])


def test_step_selection():
    parser = cli.build_parser()
    args = parser.parse_args(["restore", "x.jpg", "--skip", "split", "--colorize", "--scale", "4"])
    assert cli._steps(args) == ("fade", "repair", "faces", "color", "upscale")


def test_models_command_lists_weights(capsys):
    assert cli.main(["models"]) == 0
    assert "faces" in capsys.readouterr().out


def test_version(capsys):
    with pytest.raises(SystemExit):
        cli.main(["--version"])
    assert "0.2.0" in capsys.readouterr().out


def test_bench_options_parse():
    parser = cli.build_parser()
    args = parser.parse_args(["bench", "--cpu", "--json", "x.json"])
    assert args.cpu and args.json_path == "x.json"


def test_enabling_upscale_alone_implies_a_scale(monkeypatch):
    parser = cli.build_parser()
    args = parser.parse_args(["restore", "x.jpg", "--enable", "upscale"])
    options = cli._options(args)
    assert "upscale" in options.steps and options.scale == 2

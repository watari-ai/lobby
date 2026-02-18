"""Tests for lobby export command."""

import json
from pathlib import Path

from typer.testing import CliRunner

from backend.cli import app

runner = CliRunner()


def _make_output(tmp_path: Path) -> Path:
    """Create a fake recording output directory."""
    out = tmp_path / "my_video"
    out.mkdir()
    (out / "my_video.mp4").write_bytes(b"\x00" * 1024)
    (out / "my_video.srt").write_text("1\n00:00:00,000 --> 00:00:01,000\nHello\n")
    (out / "my_video.vtt").write_text("WEBVTT\n\n00:00:00.000 --> 00:00:01.000\nHello\n")
    (out / "thumbnail_1280x720.jpg").write_bytes(b"\xff\xd8\xff")
    return out


def test_export_basic(tmp_path):
    out = _make_output(tmp_path)
    result = runner.invoke(app, ["export", str(out)])
    assert result.exit_code == 0
    export_dir = out / "export"
    assert (export_dir / "my_video.mp4").exists()
    assert (export_dir / "my_video.srt").exists()
    assert (export_dir / "metadata.json").exists()
    assert (export_dir / "description.txt").exists()
    assert (export_dir / "thumbnail_1280x720.jpg").exists()


def test_export_metadata_content(tmp_path):
    out = _make_output(tmp_path)
    runner.invoke(app, [
        "export", str(out),
        "--title", "Test Title",
        "--description", "A test video",
        "--tags", "tag1,tag2",
    ])
    meta = json.loads((out / "export" / "metadata.json").read_text())
    assert meta["title"] == "Test Title"
    assert meta["description"] == "A test video"
    assert meta["tags"] == ["tag1", "tag2"]
    assert meta["file_size_mb"] >= 0


def test_export_custom_dest(tmp_path):
    out = _make_output(tmp_path)
    dest = tmp_path / "custom_export"
    result = runner.invoke(app, ["export", str(out), "--to", str(dest)])
    assert result.exit_code == 0
    assert (dest / "my_video.mp4").exists()


def test_export_no_srt(tmp_path):
    out = _make_output(tmp_path)
    runner.invoke(app, ["export", str(out), "--no-srt"])
    assert not (out / "export" / "my_video.srt").exists()


def test_export_with_vtt(tmp_path):
    out = _make_output(tmp_path)
    runner.invoke(app, ["export", str(out), "--vtt"])
    assert (out / "export" / "my_video.vtt").exists()


def test_export_missing_dir(tmp_path):
    result = runner.invoke(app, ["export", str(tmp_path / "nonexistent")])
    assert result.exit_code == 1


def test_export_no_video(tmp_path):
    empty = tmp_path / "empty"
    empty.mkdir()
    result = runner.invoke(app, ["export", str(empty)])
    assert result.exit_code == 1

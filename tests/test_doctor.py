"""Tests for lobby doctor command."""

from typer.testing import CliRunner

from backend.cli import app

runner = CliRunner()


def test_doctor_runs():
    """doctor command runs without crashing."""
    result = runner.invoke(app, ["doctor"])
    assert result.exit_code in (0, 1)  # 0=all ok, 1=failures found
    assert "Lobby Doctor" in result.output
    assert "Python" in result.output
    assert "FFmpeg" in result.output
    assert "Result:" in result.output


def test_doctor_with_missing_config():
    """doctor with nonexistent config still runs."""
    result = runner.invoke(app, ["doctor", "--config", "/tmp/nonexistent.yaml"])
    assert result.exit_code in (0, 1)
    assert "Lobby Doctor" in result.output


def test_doctor_checks_ffmpeg():
    """doctor reports ffmpeg status."""
    result = runner.invoke(app, ["doctor"])
    output = result.output
    # Should mention ffmpeg and ffprobe
    assert "ffmpeg" in output
    assert "ffprobe" in output

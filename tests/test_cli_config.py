"""CLI config integration tests"""

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from typer.testing import CliRunner

from backend.cli import app

runner = CliRunner()


@pytest.fixture
def tmp_script(tmp_path):
    """Create a temporary script file"""
    script = tmp_path / "test_script.txt"
    script.write_text("おはロビィ！\n[happy] 楽しいっす！\n")
    return script


@pytest.fixture
def tmp_config(tmp_path):
    """Create a temporary config file"""
    config = tmp_path / "lobby.yaml"
    avatar_base = tmp_path / "base.png"
    mouth_closed = tmp_path / "mouth_closed.png"

    # Create dummy images (1x1 RGBA PNG)
    try:
        from PIL import Image
        img = Image.new("RGBA", (100, 100), (255, 0, 0, 255))
        img.save(avatar_base)
        img.save(mouth_closed)
    except ImportError:
        avatar_base.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)
        mouth_closed.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)

    config.write_text(f"""
tts:
  provider: miotts
  base_url: http://localhost:9999
  voice: test_voice

avatar:
  base: "{avatar_base}"
  mouth_closed: "{mouth_closed}"

lipsync:
  fps: 24

video:
  fps: 24
  width: 1280
  height: 720

subtitle:
  enabled: true
  burn_in: false

output_dir: "{tmp_path}/output"
""")
    return config


class TestRecordCommand:
    """record コマンドのテスト"""

    def test_record_missing_script(self):
        result = runner.invoke(app, ["record", "nonexistent.txt"])
        assert result.exit_code == 1
        assert "not found" in result.output

    def test_record_with_config_missing_script(self, tmp_config):
        result = runner.invoke(app, [
            "record", "nonexistent.txt",
            "--config", str(tmp_config),
        ])
        assert result.exit_code == 1

    @patch("backend.cli.RecordingMode")
    def test_record_config_overrides(self, mock_mode_cls, tmp_script, tmp_config):
        """--config with CLI overrides"""
        mock_mode = AsyncMock()
        mock_mode.__aenter__ = AsyncMock(return_value=mock_mode)
        mock_mode.__aexit__ = AsyncMock(return_value=False)
        mock_mode.record_script = MagicMock(return_value=async_gen([]))
        mock_mode_cls.return_value = mock_mode

        result = runner.invoke(app, [
            "record", str(tmp_script),
            "--config", str(tmp_config),
            "--voice", "override_voice",
        ])

        # Check that config was loaded and voice was overridden
        call_kwargs = mock_mode_cls.call_args
        tts_config = call_kwargs.kwargs.get("tts_config") or call_kwargs[1].get("tts_config")
        assert tts_config.voice == "override_voice"
        assert tts_config.base_url == "http://localhost:9999"


class TestRecordVideoCommand:
    """record-video コマンドのテスト"""

    def test_record_video_missing_script(self):
        result = runner.invoke(app, ["record-video", "nonexistent.txt"])
        assert result.exit_code == 1

    def test_record_video_no_avatar_no_config(self, tmp_script):
        """Without config, avatar args are required"""
        result = runner.invoke(app, ["record-video", str(tmp_script)])
        assert result.exit_code == 1
        assert "required" in result.output.lower() or "config" in result.output.lower()

    def test_record_video_config_missing_avatar(self, tmp_script, tmp_path):
        """Config without avatar paths should error"""
        bad_config = tmp_path / "bad.yaml"
        bad_config.write_text("tts:\n  voice: test\n")

        result = runner.invoke(app, [
            "record-video", str(tmp_script),
            "--config", str(bad_config),
        ])
        assert result.exit_code == 1

    @patch("backend.cli.RecordingPipeline")
    def test_record_video_with_config(self, mock_pipeline_cls, tmp_script, tmp_config):
        """Config-based record-video"""
        mock_pipeline = AsyncMock()
        mock_pipeline.__aenter__ = AsyncMock(return_value=mock_pipeline)
        mock_pipeline.__aexit__ = AsyncMock(return_value=False)
        mock_pipeline.process_script = AsyncMock(return_value=Path("/tmp/out.mp4"))
        mock_pipeline_cls.return_value = mock_pipeline

        result = runner.invoke(app, [
            "record-video", str(tmp_script),
            "--config", str(tmp_config),
        ])

        assert result.exit_code == 0
        assert "Video created" in result.output

        # Verify pipeline config
        call_args = mock_pipeline_cls.call_args[0][0]  # PipelineConfig
        assert call_args.video.fps == 24
        assert call_args.tts.voice == "test_voice"
        assert call_args.tts.base_url == "http://localhost:9999"

    @patch("backend.cli.RecordingPipeline")
    def test_record_video_config_with_cli_overrides(self, mock_pipeline_cls, tmp_script, tmp_config):
        """Config + CLI overrides"""
        mock_pipeline = AsyncMock()
        mock_pipeline.__aenter__ = AsyncMock(return_value=mock_pipeline)
        mock_pipeline.__aexit__ = AsyncMock(return_value=False)
        mock_pipeline.process_script = AsyncMock(return_value=Path("/tmp/out.mp4"))
        mock_pipeline_cls.return_value = mock_pipeline

        result = runner.invoke(app, [
            "record-video", str(tmp_script),
            "--config", str(tmp_config),
            "--fps", "60",
            "--voice", "new_voice",
            "--burn-subtitles",
        ])

        assert result.exit_code == 0
        call_args = mock_pipeline_cls.call_args[0][0]
        assert call_args.video.fps == 60
        assert call_args.lipsync.fps == 60
        assert call_args.tts.voice == "new_voice"
        assert call_args.subtitle.burn_in is True


async def _async_gen_helper(items):
    for item in items:
        yield item


def async_gen(items):
    """Create a sync wrapper that returns an async generator"""
    return _async_gen_helper(items)

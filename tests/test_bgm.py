"""BGM mixing tests"""

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from backend.core.config import build_bgm_config
from backend.core.pipeline import BGMConfig
from backend.core.video import VideoComposer


class TestBGMConfig:
    """BGMConfig tests"""

    def test_default_disabled(self):
        config = BGMConfig()
        assert config.enabled is False
        assert config.path is None
        assert config.volume == 0.15
        assert config.duck_volume == 0.08

    def test_custom_values(self):
        config = BGMConfig(
            enabled=True,
            path=Path("/music/bgm.mp3"),
            volume=0.2,
            duck_volume=0.1,
            fade_in_ms=1000,
            fade_out_ms=5000,
        )
        assert config.enabled is True
        assert config.path == Path("/music/bgm.mp3")
        assert config.volume == 0.2
        assert config.fade_out_ms == 5000


class TestBuildBGMConfig:
    """build_bgm_config tests"""

    def test_empty_data(self):
        config = build_bgm_config({})
        assert config.enabled is False
        assert config.path is None

    def test_with_path_auto_enables(self):
        config = build_bgm_config({"bgm": {"path": "/music/bgm.mp3"}})
        assert config.enabled is True
        assert config.path == Path("/music/bgm.mp3")

    def test_explicit_disabled_with_path(self):
        config = build_bgm_config({"bgm": {"path": "/music/bgm.mp3", "enabled": False}})
        assert config.enabled is False

    def test_custom_volume(self):
        config = build_bgm_config({"bgm": {"path": "bgm.mp3", "volume": 0.3, "duck_volume": 0.05}})
        assert config.volume == 0.3
        assert config.duck_volume == 0.05

    def test_custom_fade(self):
        config = build_bgm_config({"bgm": {"path": "bgm.mp3", "fade_in_ms": 500, "fade_out_ms": 1000}})
        assert config.fade_in_ms == 500
        assert config.fade_out_ms == 1000


class TestVideoComposerMixBGM:
    """VideoComposer.mix_bgm tests"""

    @pytest.fixture
    def composer(self):
        c = VideoComposer()
        c._ffmpeg_path = "/usr/bin/ffmpeg"
        return c

    @pytest.mark.asyncio
    async def test_mix_bgm_no_ffmpeg(self):
        composer = VideoComposer()
        composer._ffmpeg_path = None
        result = await composer.mix_bgm(
            Path("video.mp4"), Path("bgm.mp3"), Path("out.mp4")
        )
        assert result is False

    @pytest.mark.asyncio
    async def test_mix_bgm_missing_video(self, composer, tmp_path):
        result = await composer.mix_bgm(
            tmp_path / "nonexistent.mp4",
            tmp_path / "bgm.mp3",
            tmp_path / "out.mp4",
        )
        assert result is False

    @pytest.mark.asyncio
    async def test_mix_bgm_missing_bgm(self, composer, tmp_path):
        video = tmp_path / "video.mp4"
        video.write_bytes(b"fake video")
        result = await composer.mix_bgm(
            video,
            tmp_path / "nonexistent.mp3",
            tmp_path / "out.mp4",
        )
        assert result is False

    @pytest.mark.asyncio
    async def test_mix_bgm_success(self, composer, tmp_path):
        video = tmp_path / "video.mp4"
        video.write_bytes(b"fake video")
        bgm = tmp_path / "bgm.mp3"
        bgm.write_bytes(b"fake bgm")
        output = tmp_path / "out.mp4"

        mock_proc = AsyncMock()
        mock_proc.communicate = AsyncMock(return_value=(b"", b""))
        mock_proc.returncode = 0

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc) as mock_exec, \
             patch("backend.core.video.get_audio_duration_ms", return_value=10000):
            result = await composer.mix_bgm(video, bgm, output)

        assert result is True
        # Verify ffmpeg was called with sidechaincompress filter
        call_args = mock_exec.call_args[0]
        filter_arg = [a for a in call_args if "sidechaincompress" in str(a)]
        assert len(filter_arg) == 1

    @pytest.mark.asyncio
    async def test_mix_bgm_ffmpeg_failure(self, composer, tmp_path):
        video = tmp_path / "video.mp4"
        video.write_bytes(b"fake video")
        bgm = tmp_path / "bgm.mp3"
        bgm.write_bytes(b"fake bgm")

        mock_proc = AsyncMock()
        mock_proc.communicate = AsyncMock(return_value=(b"", b"error"))
        mock_proc.returncode = 1

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc), \
             patch("backend.core.video.get_audio_duration_ms", return_value=5000):
            result = await composer.mix_bgm(video, bgm, tmp_path / "out.mp4")

        assert result is False

    @pytest.mark.asyncio
    async def test_mix_bgm_custom_volumes(self, composer, tmp_path):
        video = tmp_path / "video.mp4"
        video.write_bytes(b"fake video")
        bgm = tmp_path / "bgm.mp3"
        bgm.write_bytes(b"fake bgm")

        mock_proc = AsyncMock()
        mock_proc.communicate = AsyncMock(return_value=(b"", b""))
        mock_proc.returncode = 0

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc) as mock_exec, \
             patch("backend.core.video.get_audio_duration_ms", return_value=8000):
            result = await composer.mix_bgm(
                video, bgm, tmp_path / "out.mp4",
                bgm_volume=0.3, fade_in_ms=500, fade_out_ms=1000,
            )

        assert result is True
        call_args = mock_exec.call_args[0]
        filter_str = [a for a in call_args if "volume=0.3" in str(a)]
        assert len(filter_str) == 1

    @pytest.mark.asyncio
    async def test_mix_bgm_fade_out_position(self, composer, tmp_path):
        """Fade out should start at (duration - fade_out_ms)"""
        video = tmp_path / "video.mp4"
        video.write_bytes(b"fake video")
        bgm = tmp_path / "bgm.mp3"
        bgm.write_bytes(b"fake bgm")

        mock_proc = AsyncMock()
        mock_proc.communicate = AsyncMock(return_value=(b"", b""))
        mock_proc.returncode = 0

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc) as mock_exec, \
             patch("backend.core.video.get_audio_duration_ms", return_value=10000):
            await composer.mix_bgm(
                video, bgm, tmp_path / "out.mp4",
                fade_out_ms=3000,
            )

        call_args = mock_exec.call_args[0]
        filter_str = [a for a in call_args if "afade" in str(a)][0]
        # 10s - 3s = 7s fade out start
        assert "st=7.0" in filter_str

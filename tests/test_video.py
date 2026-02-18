"""Tests for backend.core.video - 動画生成エンジン"""

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.core.video import VideoComposer, VideoConfig, get_audio_duration_ms


class TestVideoConfig:
    """VideoConfig tests"""

    def test_defaults(self):
        c = VideoConfig()
        assert c.fps == 30
        assert c.width == 1920
        assert c.height == 1080
        assert c.codec == "libx264"
        assert c.audio_codec == "aac"
        assert c.crf == 23
        assert c.preset == "medium"
        assert c.pixel_format == "yuv420p"
        assert c.background_color == "#00FF00"

    def test_custom(self):
        c = VideoConfig(fps=60, width=1280, height=720, crf=18)
        assert c.fps == 60
        assert c.width == 1280
        assert c.crf == 18


class TestVideoComposer:
    """VideoComposer tests"""

    @patch("shutil.which", return_value="/usr/bin/ffmpeg")
    def test_init_ffmpeg_found(self, mock_which):
        vc = VideoComposer()
        assert vc._ffmpeg_path == "/usr/bin/ffmpeg"

    @patch("shutil.which", return_value=None)
    def test_init_ffmpeg_not_found(self, mock_which):
        vc = VideoComposer()
        assert vc._ffmpeg_path is None

    @patch("shutil.which", return_value=None)
    @pytest.mark.asyncio
    async def test_compose_no_ffmpeg(self, mock_which):
        vc = VideoComposer()
        result = await vc.compose(Path("/frames"), Path("/audio.wav"), Path("/out.mp4"))
        assert result is False

    @patch("shutil.which", return_value="/usr/bin/ffmpeg")
    @pytest.mark.asyncio
    async def test_compose_success(self, mock_which, tmp_path):
        vc = VideoComposer()
        frames_dir = tmp_path / "frames"
        frames_dir.mkdir()
        audio = tmp_path / "audio.wav"
        audio.touch()
        output = tmp_path / "output.mp4"

        mock_proc = AsyncMock()
        mock_proc.communicate = AsyncMock(return_value=(b"", b""))
        mock_proc.returncode = 0

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc) as mock_exec:
            result = await vc.compose(frames_dir, audio, output)
            assert result is True
            # Verify ffmpeg was called with correct args
            call_args = mock_exec.call_args[0]
            assert call_args[0] == "/usr/bin/ffmpeg"
            assert "-y" in call_args
            assert str(output) == call_args[-1]

    @patch("shutil.which", return_value="/usr/bin/ffmpeg")
    @pytest.mark.asyncio
    async def test_compose_with_background(self, mock_which, tmp_path):
        vc = VideoComposer()
        frames_dir = tmp_path / "frames"
        frames_dir.mkdir()
        audio = tmp_path / "audio.wav"
        audio.touch()
        bg = tmp_path / "bg.png"
        bg.touch()
        output = tmp_path / "output.mp4"

        mock_proc = AsyncMock()
        mock_proc.communicate = AsyncMock(return_value=(b"", b""))
        mock_proc.returncode = 0

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc) as mock_exec:
            result = await vc.compose(frames_dir, audio, output, background_image=bg)
            assert result is True
            call_args = mock_exec.call_args[0]
            assert "-filter_complex" in call_args

    @patch("shutil.which", return_value="/usr/bin/ffmpeg")
    @pytest.mark.asyncio
    async def test_compose_ffmpeg_failure(self, mock_which, tmp_path):
        vc = VideoComposer()

        mock_proc = AsyncMock()
        mock_proc.communicate = AsyncMock(return_value=(b"", b"error msg"))
        mock_proc.returncode = 1

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            result = await vc.compose(Path("/frames"), Path("/a.wav"), tmp_path / "out.mp4")
            assert result is False

    @patch("shutil.which", return_value="/usr/bin/ffmpeg")
    @pytest.mark.asyncio
    async def test_compose_exception(self, mock_which, tmp_path):
        vc = VideoComposer()

        with patch("asyncio.create_subprocess_exec", side_effect=OSError("boom")):
            result = await vc.compose(Path("/frames"), Path("/a.wav"), tmp_path / "out.mp4")
            assert result is False

    @patch("shutil.which", return_value=None)
    @pytest.mark.asyncio
    async def test_compose_from_segments_no_ffmpeg(self, mock_which):
        vc = VideoComposer()
        result = await vc.compose_from_segments([], Path("/out.mp4"))
        assert result is False

    @patch("shutil.which", return_value="/usr/bin/ffmpeg")
    @pytest.mark.asyncio
    async def test_compose_from_segments_empty(self, mock_which):
        vc = VideoComposer()
        result = await vc.compose_from_segments([], Path("/out.mp4"))
        assert result is False

    @patch("shutil.which", return_value="/usr/bin/ffmpeg")
    @pytest.mark.asyncio
    async def test_compose_from_segments_success(self, mock_which, tmp_path):
        vc = VideoComposer()
        output = tmp_path / "final.mp4"

        seg_frames = tmp_path / "seg0_frames"
        seg_frames.mkdir()
        seg_audio = tmp_path / "seg0.wav"
        seg_audio.touch()

        segments = [{"frames_dir": seg_frames, "audio": seg_audio}]

        mock_proc = AsyncMock()
        mock_proc.communicate = AsyncMock(return_value=(b"", b""))
        mock_proc.returncode = 0

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            result = await vc.compose_from_segments(segments, output)
            assert result is True

    @patch("shutil.which", return_value="/usr/bin/ffmpeg")
    @pytest.mark.asyncio
    async def test_compose_from_segments_all_fail(self, mock_which, tmp_path):
        vc = VideoComposer()
        output = tmp_path / "final.mp4"

        segments = [{"frames_dir": tmp_path / "f", "audio": tmp_path / "a.wav"}]

        mock_proc = AsyncMock()
        mock_proc.communicate = AsyncMock(return_value=(b"", b"err"))
        mock_proc.returncode = 1

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            result = await vc.compose_from_segments(segments, output)
            assert result is False

    @patch("shutil.which", return_value="/usr/bin/ffmpeg")
    @pytest.mark.asyncio
    async def test_compose_from_segments_concat_fails(self, mock_which, tmp_path):
        vc = VideoComposer()
        output = tmp_path / "final.mp4"

        segments = [{"frames_dir": tmp_path / "f", "audio": tmp_path / "a.wav"}]

        call_count = 0

        async def mock_exec(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            proc = AsyncMock()
            if call_count == 1:
                # compose succeeds
                proc.communicate = AsyncMock(return_value=(b"", b""))
                proc.returncode = 0
            else:
                # concat fails
                proc.communicate = AsyncMock(return_value=(b"", b"concat err"))
                proc.returncode = 1
            return proc

        with patch("asyncio.create_subprocess_exec", side_effect=mock_exec):
            result = await vc.compose_from_segments(segments, output)
            assert result is False

    @patch("shutil.which", return_value=None)
    @pytest.mark.asyncio
    async def test_add_background_no_ffmpeg(self, mock_which):
        vc = VideoComposer()
        result = await vc.add_background(Path("/in.mp4"), Path("/bg.png"), Path("/out.mp4"))
        assert result is False

    @patch("shutil.which", return_value="/usr/bin/ffmpeg")
    @pytest.mark.asyncio
    async def test_add_background_success(self, mock_which, tmp_path):
        vc = VideoComposer()

        mock_proc = AsyncMock()
        mock_proc.communicate = AsyncMock(return_value=(b"", b""))
        mock_proc.returncode = 0

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc) as mock_exec:
            result = await vc.add_background(
                Path("/in.mp4"), Path("/bg.png"), Path("/out.mp4"), position=(100, 200)
            )
            assert result is True
            call_args = mock_exec.call_args[0]
            assert "chromakey" in str(call_args)
            assert "100" in str(call_args)
            assert "200" in str(call_args)

    @patch("shutil.which", return_value="/usr/bin/ffmpeg")
    @pytest.mark.asyncio
    async def test_add_background_failure(self, mock_which):
        vc = VideoComposer()

        mock_proc = AsyncMock()
        mock_proc.communicate = AsyncMock(return_value=(b"", b"err"))
        mock_proc.returncode = 1

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            result = await vc.add_background(Path("/in.mp4"), Path("/bg.png"), Path("/out.mp4"))
            assert result is False

    @patch("shutil.which", return_value="/usr/bin/ffmpeg")
    @pytest.mark.asyncio
    async def test_add_background_exception(self, mock_which):
        vc = VideoComposer()

        with patch("asyncio.create_subprocess_exec", side_effect=OSError("boom")):
            result = await vc.add_background(Path("/in.mp4"), Path("/bg.png"), Path("/out.mp4"))
            assert result is False

    @patch("shutil.which", return_value=None)
    @pytest.mark.asyncio
    async def test_burn_subtitles_no_ffmpeg(self, mock_which):
        vc = VideoComposer()
        result = await vc.burn_subtitles(Path("/v.mp4"), Path("/s.srt"), Path("/out.mp4"))
        assert result is False

    @patch("shutil.which", return_value="/usr/bin/ffmpeg")
    @pytest.mark.asyncio
    async def test_burn_subtitles_video_not_found(self, mock_which, tmp_path):
        vc = VideoComposer()
        result = await vc.burn_subtitles(
            tmp_path / "nonexistent.mp4", tmp_path / "s.srt", tmp_path / "out.mp4"
        )
        assert result is False

    @patch("shutil.which", return_value="/usr/bin/ffmpeg")
    @pytest.mark.asyncio
    async def test_burn_subtitles_subtitle_not_found(self, mock_which, tmp_path):
        vc = VideoComposer()
        video = tmp_path / "v.mp4"
        video.touch()
        result = await vc.burn_subtitles(video, tmp_path / "nonexistent.srt", tmp_path / "out.mp4")
        assert result is False

    @patch("shutil.which", return_value="/usr/bin/ffmpeg")
    @pytest.mark.asyncio
    async def test_burn_subtitles_success(self, mock_which, tmp_path):
        vc = VideoComposer()
        video = tmp_path / "v.mp4"
        video.touch()
        srt = tmp_path / "s.srt"
        srt.touch()
        output = tmp_path / "out.mp4"

        mock_proc = AsyncMock()
        mock_proc.communicate = AsyncMock(return_value=(b"", b""))
        mock_proc.returncode = 0

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc) as mock_exec:
            result = await vc.burn_subtitles(video, srt, output)
            assert result is True
            call_args = mock_exec.call_args[0]
            assert "subtitles" in str(call_args)

    @patch("shutil.which", return_value="/usr/bin/ffmpeg")
    @pytest.mark.asyncio
    async def test_burn_subtitles_failure(self, mock_which, tmp_path):
        vc = VideoComposer()
        video = tmp_path / "v.mp4"
        video.touch()
        srt = tmp_path / "s.srt"
        srt.touch()

        mock_proc = AsyncMock()
        mock_proc.communicate = AsyncMock(return_value=(b"", b"error"))
        mock_proc.returncode = 1

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            result = await vc.burn_subtitles(video, srt, tmp_path / "out.mp4")
            assert result is False

    @patch("shutil.which", return_value="/usr/bin/ffmpeg")
    @pytest.mark.asyncio
    async def test_burn_subtitles_exception(self, mock_which, tmp_path):
        vc = VideoComposer()
        video = tmp_path / "v.mp4"
        video.touch()
        srt = tmp_path / "s.srt"
        srt.touch()

        with patch("asyncio.create_subprocess_exec", side_effect=OSError("boom")):
            result = await vc.burn_subtitles(video, srt, tmp_path / "out.mp4")
            assert result is False

    @patch("shutil.which", return_value="/usr/bin/ffmpeg")
    @pytest.mark.asyncio
    async def test_burn_subtitles_custom_style(self, mock_which, tmp_path):
        vc = VideoComposer()
        video = tmp_path / "v.mp4"
        video.touch()
        srt = tmp_path / "s.srt"
        srt.touch()

        mock_proc = AsyncMock()
        mock_proc.communicate = AsyncMock(return_value=(b"", b""))
        mock_proc.returncode = 0

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc) as mock_exec:
            result = await vc.burn_subtitles(
                video, srt, tmp_path / "out.mp4",
                font_size=72, font_name="Arial", margin_bottom=100, outline_width=5
            )
            assert result is True
            call_str = str(mock_exec.call_args[0])
            assert "FontSize=72" in call_str
            assert "Arial" in call_str


class TestGetAudioDurationMs:
    """get_audio_duration_ms tests"""

    @patch("shutil.which", return_value=None)
    @pytest.mark.asyncio
    async def test_no_ffprobe(self, mock_which):
        result = await get_audio_duration_ms(Path("/audio.wav"))
        assert result == 0

    @patch("shutil.which", return_value="/usr/bin/ffprobe")
    @pytest.mark.asyncio
    async def test_success(self, mock_which):
        mock_proc = AsyncMock()
        mock_proc.communicate = AsyncMock(return_value=(b"3.5\n", b""))
        mock_proc.returncode = 0

        with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
            result = await get_audio_duration_ms(Path("/audio.wav"))
            assert result == 3500

    @patch("shutil.which", return_value="/usr/bin/ffprobe")
    @pytest.mark.asyncio
    async def test_exception(self, mock_which):
        with patch("asyncio.create_subprocess_exec", side_effect=OSError("boom")):
            result = await get_audio_duration_ms(Path("/audio.wav"))
            assert result == 0

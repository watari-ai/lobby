"""Tests for clip extraction module."""

import tempfile
from pathlib import Path

import pytest

from backend.core.clip import ClipConfig, ClipExtractor, ClipManager, ClipResult
from backend.core.highlight import Highlight, HighlightType


class TestClipConfig:
    """Test ClipConfig defaults."""

    def test_default_config(self):
        config = ClipConfig()

        assert config.pre_buffer_ms == 2000
        assert config.post_buffer_ms == 3000
        assert config.default_format == "mp4"
        assert config.crf == 23
        assert config.max_clips == 10

    def test_custom_config(self):
        config = ClipConfig(
            pre_buffer_ms=1000,
            post_buffer_ms=2000,
            default_format="webm",
            crf=18
        )

        assert config.pre_buffer_ms == 1000
        assert config.post_buffer_ms == 2000
        assert config.default_format == "webm"
        assert config.crf == 18


class TestClipResult:
    """Test ClipResult dataclass."""

    def test_success_result(self):
        result = ClipResult(
            success=True,
            output_path=Path("/tmp/clip.mp4"),
            duration_ms=5000
        )

        assert result.success is True
        assert result.output_path == Path("/tmp/clip.mp4")
        assert result.duration_ms == 5000
        assert result.error is None

    def test_failure_result(self):
        result = ClipResult(
            success=False,
            error="Video not found"
        )

        assert result.success is False
        assert result.output_path is None
        assert result.error == "Video not found"

    def test_to_dict(self):
        highlight = Highlight(
            timestamp_ms=5000,
            duration_ms=3000,
            highlight_type=HighlightType.AUDIO_SPIKE,
            score=0.8,
            label="Test"
        )

        result = ClipResult(
            success=True,
            output_path=Path("/tmp/clip.mp4"),
            duration_ms=5000,
            highlight=highlight
        )

        data = result.to_dict()
        assert data["success"] is True
        assert data["output_path"] == "/tmp/clip.mp4"
        assert data["duration_ms"] == 5000
        assert data["highlight"]["score"] == 0.8


class TestClipExtractor:
    """Test ClipExtractor functionality."""

    def test_init(self):
        extractor = ClipExtractor()
        assert extractor.config is not None

    def test_init_with_config(self):
        config = ClipConfig(pre_buffer_ms=500)
        extractor = ClipExtractor(config=config)
        assert extractor.config.pre_buffer_ms == 500

    def test_ms_to_timestamp(self):
        extractor = ClipExtractor()

        # 0ms
        assert extractor._ms_to_timestamp(0) == "00:00:00.000"

        # 1 second
        assert extractor._ms_to_timestamp(1000) == "00:00:01.000"

        # 1 minute
        assert extractor._ms_to_timestamp(60000) == "00:01:00.000"

        # 1 hour
        assert extractor._ms_to_timestamp(3600000) == "01:00:00.000"

        # Complex time
        assert extractor._ms_to_timestamp(3723500) == "01:02:03.500"

    def test_build_video_command_mp4(self):
        extractor = ClipExtractor()
        cmd = extractor._build_video_command(
            input_path=Path("/tmp/video.mp4"),
            output_path=Path("/tmp/clip.mp4"),
            start_ts="00:01:00.000",
            duration_ts="00:00:30.000",
            format="mp4"
        )

        assert "ffmpeg" in cmd
        assert "-ss" in cmd
        assert "00:01:00.000" in cmd
        assert "-t" in cmd
        assert "00:00:30.000" in cmd
        assert "-c:v" in cmd
        assert "libx264" in cmd

    def test_build_video_command_webm(self):
        extractor = ClipExtractor()
        cmd = extractor._build_video_command(
            input_path=Path("/tmp/video.mp4"),
            output_path=Path("/tmp/clip.webm"),
            start_ts="00:00:10.000",
            duration_ts="00:00:05.000",
            format="webm"
        )

        assert "ffmpeg" in cmd
        assert "libvpx-vp9" in cmd
        assert "libopus" in cmd


class TestClipExtractorAsync:
    """Async tests for ClipExtractor."""

    @pytest.fixture
    def extractor(self):
        return ClipExtractor()

    @pytest.mark.asyncio
    async def test_extract_clip_video_not_found(self, extractor):
        result = await extractor.extract_clip(
            video_path=Path("/nonexistent/video.mp4"),
            start_ms=0,
            end_ms=5000
        )

        assert result.success is False
        assert "not found" in result.error.lower()

    @pytest.mark.asyncio
    async def test_extract_clip_invalid_time_range(self, extractor):
        # Create a temporary file to simulate video
        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as f:
            temp_path = Path(f.name)
            f.write(b"fake video content")

        try:
            result = await extractor.extract_clip(
                video_path=temp_path,
                start_ms=5000,
                end_ms=1000  # end before start
            )

            # Should fail due to invalid range or video duration
            assert result.success is False
        finally:
            temp_path.unlink()


class TestClipManager:
    """Test ClipManager functionality."""

    def test_init(self):
        manager = ClipManager()
        assert manager.detector is not None
        assert manager.extractor is not None

    def test_init_with_components(self):
        from backend.core.highlight import HighlightDetector

        detector = HighlightDetector()
        extractor = ClipExtractor()

        manager = ClipManager(detector=detector, extractor=extractor)
        assert manager.detector is detector
        assert manager.extractor is extractor

    @pytest.mark.asyncio
    async def test_extract_time_range(self):
        manager = ClipManager()

        result = await manager.extract_time_range(
            video_path=Path("/nonexistent/video.mp4"),
            start_ms=0,
            end_ms=5000
        )

        assert result.success is False
        assert "not found" in result.error.lower()


class TestClipIntegration:
    """Integration tests requiring actual video files."""

    @pytest.fixture
    def sample_highlights(self):
        return [
            Highlight(
                timestamp_ms=5000,
                duration_ms=3000,
                highlight_type=HighlightType.AUDIO_SPIKE,
                score=0.9,
                label="Loud moment 1"
            ),
            Highlight(
                timestamp_ms=15000,
                duration_ms=2000,
                highlight_type=HighlightType.EMOTION_PEAK,
                score=0.8,
                label="Excited moment"
            ),
            Highlight(
                timestamp_ms=30000,
                duration_ms=4000,
                highlight_type=HighlightType.CHAT_BURST,
                score=0.7,
                label="Chat burst"
            )
        ]

    def test_highlight_ordering(self, sample_highlights):
        """Test that highlights are properly sorted."""
        sorted_by_score = sorted(sample_highlights, key=lambda h: h.score, reverse=True)
        assert sorted_by_score[0].score == 0.9
        assert sorted_by_score[-1].score == 0.7

        sorted_by_time = sorted(sample_highlights, key=lambda h: h.timestamp_ms)
        assert sorted_by_time[0].timestamp_ms == 5000
        assert sorted_by_time[-1].timestamp_ms == 30000


# Run tests
if __name__ == "__main__":
    pytest.main([__file__, "-v"])

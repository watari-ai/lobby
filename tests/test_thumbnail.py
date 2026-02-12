"""Tests for thumbnail generation."""

import asyncio
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.core.thumbnail import (
    FrameQuality,
    ThumbnailConfig,
    ThumbnailGenerator,
    ThumbnailManager,
    ThumbnailResult,
    ThumbnailSize,
)
from backend.core.highlight import Highlight, HighlightType


class TestThumbnailSize:
    """Tests for ThumbnailSize class."""
    
    def test_youtube_preset(self):
        """Test YouTube preset size."""
        size = ThumbnailSize.youtube()
        assert size.name == "youtube"
        assert size.width == 1280
        assert size.height == 720
    
    def test_twitter_preset(self):
        """Test Twitter preset size."""
        size = ThumbnailSize.twitter()
        assert size.name == "twitter"
        assert size.width == 1200
        assert size.height == 675
    
    def test_square_preset(self):
        """Test square preset size."""
        size = ThumbnailSize.square()
        assert size.name == "square"
        assert size.width == 1080
        assert size.height == 1080
    
    def test_vertical_preset(self):
        """Test vertical preset size."""
        size = ThumbnailSize.vertical()
        assert size.name == "vertical"
        assert size.width == 1080
        assert size.height == 1920
    
    def test_discord_preset(self):
        """Test Discord preset size."""
        size = ThumbnailSize.discord()
        assert size.name == "discord"
        assert size.width == 800
        assert size.height == 450


class TestFrameQuality:
    """Tests for FrameQuality class."""
    
    def test_overall_score_middle_brightness(self):
        """Test that middle brightness gets highest score."""
        quality = FrameQuality(brightness=0.5, contrast=0.3, blur_score=200)
        assert quality.overall_score > 0.8  # Should be high
    
    def test_overall_score_low_brightness(self):
        """Test that low brightness reduces score compared to middle."""
        low_quality = FrameQuality(brightness=0.1, contrast=0.3, blur_score=200)
        mid_quality = FrameQuality(brightness=0.5, contrast=0.3, blur_score=200)
        assert low_quality.overall_score < mid_quality.overall_score
    
    def test_overall_score_high_brightness(self):
        """Test that high brightness reduces score compared to middle."""
        high_quality = FrameQuality(brightness=0.9, contrast=0.3, blur_score=200)
        mid_quality = FrameQuality(brightness=0.5, contrast=0.3, blur_score=200)
        assert high_quality.overall_score < mid_quality.overall_score
    
    def test_overall_score_low_contrast(self):
        """Test that low contrast reduces score."""
        quality = FrameQuality(brightness=0.5, contrast=0.05, blur_score=200)
        assert quality.overall_score < 0.9  # Penalized
    
    def test_overall_score_blurry(self):
        """Test that blur reduces score."""
        quality = FrameQuality(brightness=0.5, contrast=0.3, blur_score=10)
        assert quality.overall_score < 0.8  # Penalized


class TestThumbnailConfig:
    """Tests for ThumbnailConfig class."""
    
    def test_default_config(self):
        """Test default configuration values."""
        config = ThumbnailConfig()
        assert config.output_format == "png"
        assert config.jpeg_quality == 95
        assert config.frames_per_highlight == 5
        assert len(config.default_sizes) == 3
    
    def test_custom_config(self):
        """Test custom configuration."""
        config = ThumbnailConfig(
            output_format="jpg",
            jpeg_quality=80,
            frames_per_highlight=10,
            overlay_enabled=True,
        )
        assert config.output_format == "jpg"
        assert config.jpeg_quality == 80
        assert config.frames_per_highlight == 10
        assert config.overlay_enabled is True


class TestThumbnailResult:
    """Tests for ThumbnailResult class."""
    
    def test_successful_result(self):
        """Test successful result creation."""
        result = ThumbnailResult(
            success=True,
            output_paths=[Path("/tmp/thumb.png")],
            selected_frame_ms=5000,
            quality=FrameQuality(brightness=0.5, contrast=0.3, blur_score=150),
        )
        assert result.success is True
        assert len(result.output_paths) == 1
        assert result.selected_frame_ms == 5000
        assert result.quality is not None
    
    def test_failed_result(self):
        """Test failed result creation."""
        result = ThumbnailResult(
            success=False,
            error="Video not found",
        )
        assert result.success is False
        assert result.error == "Video not found"
        assert len(result.output_paths) == 0
    
    def test_to_dict(self):
        """Test conversion to dictionary."""
        result = ThumbnailResult(
            success=True,
            output_paths=[Path("/tmp/thumb.png")],
            selected_frame_ms=5000,
            quality=FrameQuality(brightness=0.5, contrast=0.3, blur_score=150),
        )
        data = result.to_dict()
        assert data["success"] is True
        assert len(data["output_paths"]) == 1
        assert data["selected_frame_ms"] == 5000
        assert "quality" in data
        assert "overall_score" in data["quality"]


class TestThumbnailGenerator:
    """Tests for ThumbnailGenerator class."""
    
    def test_init_default_config(self):
        """Test initialization with default config."""
        generator = ThumbnailGenerator()
        assert generator.config is not None
        assert generator.config.output_format == "png"
    
    def test_init_custom_config(self):
        """Test initialization with custom config."""
        config = ThumbnailConfig(output_format="jpg")
        generator = ThumbnailGenerator(config=config)
        assert generator.config.output_format == "jpg"
    
    def test_ms_to_timestamp(self):
        """Test millisecond to timestamp conversion."""
        generator = ThumbnailGenerator()
        
        # Test various timestamps
        assert generator._ms_to_timestamp(0) == "00:00:00.000"
        assert generator._ms_to_timestamp(1500) == "00:00:01.500"
        assert generator._ms_to_timestamp(65000) == "00:01:05.000"
        assert generator._ms_to_timestamp(3661500) == "01:01:01.500"
    
    def test_is_frame_acceptable_good_frame(self):
        """Test frame acceptance for good quality."""
        generator = ThumbnailGenerator()
        quality = FrameQuality(brightness=0.5, contrast=0.2, blur_score=100)
        assert generator._is_frame_acceptable(quality) is True
    
    def test_is_frame_acceptable_too_dark(self):
        """Test frame rejection for too dark frame."""
        generator = ThumbnailGenerator()
        quality = FrameQuality(brightness=0.05, contrast=0.2, blur_score=100)
        assert generator._is_frame_acceptable(quality) is False
    
    def test_is_frame_acceptable_too_bright(self):
        """Test frame rejection for too bright frame."""
        generator = ThumbnailGenerator()
        quality = FrameQuality(brightness=0.95, contrast=0.2, blur_score=100)
        assert generator._is_frame_acceptable(quality) is False
    
    def test_is_frame_acceptable_low_contrast(self):
        """Test frame rejection for low contrast."""
        generator = ThumbnailGenerator()
        quality = FrameQuality(brightness=0.5, contrast=0.05, blur_score=100)
        assert generator._is_frame_acceptable(quality) is False


class TestThumbnailGeneratorAsync:
    """Async tests for ThumbnailGenerator."""
    
    @pytest.mark.asyncio
    async def test_extract_frame_video_not_found(self):
        """Test frame extraction with missing video."""
        generator = ThumbnailGenerator()
        
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "frame.png"
            result = await generator.extract_frame(
                Path("/nonexistent/video.mp4"),
                1000,
                output_path,
            )
            assert result is False
    
    @pytest.mark.asyncio
    async def test_generate_from_video_not_found(self):
        """Test thumbnail generation with missing video."""
        generator = ThumbnailGenerator()
        
        result = await generator.generate_from_video(
            Path("/nonexistent/video.mp4"),
        )
        
        assert result.success is False
        assert "not found" in result.error.lower()
    
    @pytest.mark.asyncio
    async def test_generate_at_timestamp_video_not_found(self):
        """Test timestamp-based generation with missing video."""
        generator = ThumbnailGenerator()
        
        result = await generator.generate_at_timestamp(
            Path("/nonexistent/video.mp4"),
            timestamp_ms=5000,
        )
        
        assert result.success is False
    
    @pytest.mark.asyncio
    async def test_generate_from_highlight_video_not_found(self):
        """Test highlight-based generation with missing video."""
        generator = ThumbnailGenerator()
        
        highlight = Highlight(
            timestamp_ms=5000,
            duration_ms=1000,
            highlight_type=HighlightType.AUDIO_SPIKE,
            score=0.9,
            label="test highlight",
        )
        
        result = await generator.generate_from_highlight(
            Path("/nonexistent/video.mp4"),
            highlight=highlight,
        )
        
        assert result.success is False
        assert "not found" in result.error.lower()


class TestThumbnailManager:
    """Tests for ThumbnailManager class."""
    
    def test_init_default(self):
        """Test initialization with defaults."""
        manager = ThumbnailManager()
        assert manager.generator is not None
    
    def test_init_custom_generator(self):
        """Test initialization with custom generator."""
        config = ThumbnailConfig(output_format="webp")
        generator = ThumbnailGenerator(config=config)
        manager = ThumbnailManager(generator=generator)
        
        assert manager.generator.config.output_format == "webp"
    
    @pytest.mark.asyncio
    async def test_auto_generate_video_not_found(self):
        """Test auto generation with missing video."""
        manager = ThumbnailManager()
        
        result = await manager.auto_generate(
            Path("/nonexistent/video.mp4"),
        )
        
        assert result.success is False


class TestThumbnailAPI:
    """Tests for Thumbnail API endpoints."""
    
    @pytest.fixture
    def client(self):
        """Create test client."""
        from fastapi.testclient import TestClient
        from backend.api.main import app
        return TestClient(app)
    
    def test_get_status(self, client):
        """Test status endpoint."""
        response = client.get("/api/thumbnail/status")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ready"
        assert "dependencies" in data
        assert "config" in data
    
    def test_get_preset_sizes(self, client):
        """Test preset sizes endpoint."""
        response = client.get("/api/thumbnail/sizes")
        assert response.status_code == 200
        data = response.json()
        assert "presets" in data
        assert len(data["presets"]) >= 5
        
        # Verify YouTube preset
        youtube = next((p for p in data["presets"] if p["name"] == "youtube"), None)
        assert youtube is not None
        assert youtube["width"] == 1280
        assert youtube["height"] == 720
    
    def test_generate_video_not_found(self, client):
        """Test generate with missing video."""
        response = client.post(
            "/api/thumbnail/generate",
            json={"video_path": "/nonexistent/video.mp4"}
        )
        assert response.status_code == 404
    
    def test_generate_at_timestamp_video_not_found(self, client):
        """Test generate-at-timestamp with missing video."""
        response = client.post(
            "/api/thumbnail/generate-at-timestamp",
            json={"video_path": "/nonexistent/video.mp4", "timestamp_ms": 5000}
        )
        assert response.status_code == 404
    
    def test_generate_from_highlight_video_not_found(self, client):
        """Test generate-from-highlight with missing video."""
        response = client.post(
            "/api/thumbnail/generate-from-highlight",
            json={
                "video_path": "/nonexistent/video.mp4",
                "highlight": {
                    "timestamp_ms": 5000,
                    "duration_ms": 1000,
                    "type": "audio_spike",
                    "score": 0.9,
                    "label": "test",
                }
            }
        )
        assert response.status_code == 404
    
    def test_configure(self, client):
        """Test configuration endpoint."""
        response = client.post(
            "/api/thumbnail/configure",
            json={
                "output_format": "jpg",
                "jpeg_quality": 90,
                "frames_per_highlight": 7,
                "overlay_enabled": True,
                "overlay_font_size": 60,
                "overlay_position": "top",
            }
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "configured"
        assert data["config"]["output_format"] == "jpg"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

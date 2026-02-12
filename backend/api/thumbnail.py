"""
Thumbnail Generation API for Lobby.

Endpoints for automatic thumbnail generation from videos.
"""

from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..core.thumbnail import (
    ThumbnailConfig,
    ThumbnailGenerator,
    ThumbnailManager,
    ThumbnailResult,
    ThumbnailSize,
)
from ..core.highlight import Highlight, HighlightType

router = APIRouter(prefix="/api/thumbnail", tags=["thumbnail"])

# Global instances
_thumbnail_manager: Optional[ThumbnailManager] = None


def get_thumbnail_manager() -> ThumbnailManager:
    """Get or create ThumbnailManager instance."""
    global _thumbnail_manager
    if _thumbnail_manager is None:
        _thumbnail_manager = ThumbnailManager()
    return _thumbnail_manager


# === Request/Response Models ===

class ThumbnailSizeModel(BaseModel):
    """Thumbnail size specification."""
    name: str = Field(..., description="Size name (e.g., youtube, twitter)")
    width: int = Field(..., gt=0, description="Width in pixels")
    height: int = Field(..., gt=0, description="Height in pixels")


class ThumbnailConfigModel(BaseModel):
    """Configuration for thumbnail generation."""
    output_format: str = Field(default="png", description="Output format (png, jpg, webp)")
    jpeg_quality: int = Field(default=95, ge=1, le=100, description="JPEG quality (1-100)")
    frames_per_highlight: int = Field(default=5, ge=1, le=20, description="Frames to analyze per highlight")
    overlay_enabled: bool = Field(default=False, description="Enable text overlay")
    overlay_font_size: int = Field(default=72, ge=12, le=200, description="Overlay font size")
    overlay_position: str = Field(default="bottom", description="Overlay position (top, center, bottom)")


class GenerateThumbnailRequest(BaseModel):
    """Request to generate thumbnail from video."""
    video_path: str = Field(..., description="Path to source video")
    output_dir: Optional[str] = Field(default=None, description="Output directory")
    sizes: Optional[list[ThumbnailSizeModel]] = Field(
        default=None, 
        description="Thumbnail sizes to generate (default: YouTube, Twitter, Square)"
    )
    text_overlay: Optional[str] = Field(default=None, description="Text to overlay on thumbnail")
    session_log_path: Optional[str] = Field(default=None, description="Session log for highlight detection")


class GenerateAtTimestampRequest(BaseModel):
    """Request to generate thumbnail at specific timestamp."""
    video_path: str = Field(..., description="Path to source video")
    timestamp_ms: int = Field(..., ge=0, description="Timestamp in milliseconds")
    output_dir: Optional[str] = Field(default=None, description="Output directory")
    sizes: Optional[list[ThumbnailSizeModel]] = Field(default=None, description="Thumbnail sizes")
    text_overlay: Optional[str] = Field(default=None, description="Text overlay")


class GenerateFromHighlightRequest(BaseModel):
    """Request to generate thumbnail from a highlight."""
    video_path: str = Field(..., description="Path to source video")
    highlight: dict = Field(..., description="Highlight object (timestamp_ms, duration_ms, type, score, label)")
    output_dir: Optional[str] = Field(default=None, description="Output directory")
    sizes: Optional[list[ThumbnailSizeModel]] = Field(default=None, description="Thumbnail sizes")
    text_overlay: Optional[str] = Field(default=None, description="Text overlay")


class ThumbnailQualityModel(BaseModel):
    """Quality metrics for generated thumbnail."""
    brightness: float = Field(..., description="Brightness (0.0-1.0)")
    contrast: float = Field(..., description="Contrast score")
    blur_score: float = Field(..., description="Sharpness score (higher = sharper)")
    overall_score: float = Field(..., description="Combined quality score (0.0-1.0)")


class ThumbnailResponse(BaseModel):
    """Response for thumbnail generation."""
    success: bool
    output_paths: list[str] = Field(default_factory=list)
    selected_frame_ms: int = Field(default=0)
    quality: Optional[ThumbnailQualityModel] = None
    error: Optional[str] = None


# === Helper Functions ===

def _convert_sizes(size_models: Optional[list[ThumbnailSizeModel]]) -> Optional[list[ThumbnailSize]]:
    """Convert size models to ThumbnailSize objects."""
    if size_models is None:
        return None
    return [ThumbnailSize(name=s.name, width=s.width, height=s.height) for s in size_models]


def _result_to_response(result: ThumbnailResult) -> ThumbnailResponse:
    """Convert ThumbnailResult to API response."""
    quality = None
    if result.quality:
        quality = ThumbnailQualityModel(
            brightness=result.quality.brightness,
            contrast=result.quality.contrast,
            blur_score=result.quality.blur_score,
            overall_score=result.quality.overall_score,
        )
    
    return ThumbnailResponse(
        success=result.success,
        output_paths=[str(p) for p in result.output_paths],
        selected_frame_ms=result.selected_frame_ms,
        quality=quality,
        error=result.error,
    )


# === API Endpoints ===

@router.post("/generate", response_model=ThumbnailResponse)
async def generate_thumbnail(request: GenerateThumbnailRequest):
    """
    Automatically generate thumbnails from a video.
    
    Analyzes the video for highlights and selects the best frame
    for thumbnail generation. Multiple sizes are generated.
    """
    manager = get_thumbnail_manager()
    
    video_path = Path(request.video_path)
    if not video_path.exists():
        raise HTTPException(status_code=404, detail=f"Video not found: {request.video_path}")
    
    sizes = _convert_sizes(request.sizes)
    output_dir = Path(request.output_dir) if request.output_dir else None
    session_log_path = Path(request.session_log_path) if request.session_log_path else None
    
    result = await manager.auto_generate(
        video_path=video_path,
        session_log_path=session_log_path,
        output_dir=output_dir,
        sizes=sizes,
        text_overlay=request.text_overlay,
    )
    
    return _result_to_response(result)


@router.post("/generate-at-timestamp", response_model=ThumbnailResponse)
async def generate_at_timestamp(request: GenerateAtTimestampRequest):
    """
    Generate thumbnail at a specific timestamp.
    
    Extracts frames around the specified timestamp and selects
    the best quality frame for thumbnail generation.
    """
    manager = get_thumbnail_manager()
    generator = manager.generator
    
    video_path = Path(request.video_path)
    if not video_path.exists():
        raise HTTPException(status_code=404, detail=f"Video not found: {request.video_path}")
    
    sizes = _convert_sizes(request.sizes)
    output_dir = Path(request.output_dir) if request.output_dir else None
    
    result = await generator.generate_at_timestamp(
        video_path=video_path,
        timestamp_ms=request.timestamp_ms,
        output_dir=output_dir,
        sizes=sizes,
        text_overlay=request.text_overlay,
    )
    
    return _result_to_response(result)


@router.post("/generate-from-highlight", response_model=ThumbnailResponse)
async def generate_from_highlight(request: GenerateFromHighlightRequest):
    """
    Generate thumbnail from a specific highlight.
    
    Uses the highlight's timestamp and duration to find
    the best frame for thumbnail generation.
    """
    manager = get_thumbnail_manager()
    generator = manager.generator
    
    video_path = Path(request.video_path)
    if not video_path.exists():
        raise HTTPException(status_code=404, detail=f"Video not found: {request.video_path}")
    
    # Parse highlight
    try:
        highlight = Highlight(
            timestamp_ms=request.highlight.get("timestamp_ms", 0),
            duration_ms=request.highlight.get("duration_ms", 1000),
            highlight_type=HighlightType(request.highlight.get("type", "manual_marker")),
            score=request.highlight.get("score", 1.0),
            label=request.highlight.get("label", "highlight"),
            metadata=request.highlight.get("metadata", {}),
        )
    except (KeyError, ValueError) as e:
        raise HTTPException(status_code=400, detail=f"Invalid highlight format: {e}")
    
    sizes = _convert_sizes(request.sizes)
    output_dir = Path(request.output_dir) if request.output_dir else None
    
    result = await generator.generate_from_highlight(
        video_path=video_path,
        highlight=highlight,
        output_dir=output_dir,
        sizes=sizes,
        text_overlay=request.text_overlay,
    )
    
    return _result_to_response(result)


@router.get("/sizes")
async def get_preset_sizes():
    """
    Get available preset thumbnail sizes.
    
    Returns predefined sizes for common platforms.
    """
    return {
        "presets": [
            {"name": "youtube", "width": 1280, "height": 720, "description": "YouTube (16:9)"},
            {"name": "twitter", "width": 1200, "height": 675, "description": "Twitter/X (16:9)"},
            {"name": "square", "width": 1080, "height": 1080, "description": "Instagram Square (1:1)"},
            {"name": "vertical", "width": 1080, "height": 1920, "description": "TikTok/Reels (9:16)"},
            {"name": "discord", "width": 800, "height": 450, "description": "Discord Embed (16:9)"},
        ]
    }


@router.post("/configure")
async def configure_thumbnail_generator(config: ThumbnailConfigModel):
    """
    Configure the thumbnail generator.
    
    Updates settings for thumbnail generation.
    """
    global _thumbnail_manager
    
    thumbnail_config = ThumbnailConfig(
        output_format=config.output_format,
        jpeg_quality=config.jpeg_quality,
        frames_per_highlight=config.frames_per_highlight,
        overlay_enabled=config.overlay_enabled,
        overlay_font_size=config.overlay_font_size,
        overlay_position=config.overlay_position,
    )
    
    generator = ThumbnailGenerator(config=thumbnail_config)
    _thumbnail_manager = ThumbnailManager(generator=generator)
    
    return {
        "status": "configured",
        "config": {
            "output_format": config.output_format,
            "jpeg_quality": config.jpeg_quality,
            "frames_per_highlight": config.frames_per_highlight,
            "overlay_enabled": config.overlay_enabled,
        }
    }


@router.get("/status")
async def get_status():
    """
    Get thumbnail generator status.
    
    Returns availability and configuration.
    """
    import shutil
    
    try:
        from PIL import Image
        pillow_available = True
    except ImportError:
        pillow_available = False
    
    manager = get_thumbnail_manager()
    config = manager.generator.config
    
    return {
        "status": "ready",
        "dependencies": {
            "ffmpeg": shutil.which("ffmpeg") is not None,
            "pillow": pillow_available,
        },
        "config": {
            "output_format": config.output_format,
            "jpeg_quality": config.jpeg_quality,
            "frames_per_highlight": config.frames_per_highlight,
            "overlay_enabled": config.overlay_enabled,
            "default_sizes": [
                {"name": s.name, "width": s.width, "height": s.height}
                for s in config.default_sizes
            ],
        }
    }

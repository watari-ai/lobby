"""
Clip Extraction API for Lobby.

Endpoints for extracting video clips from highlights.
"""

from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..core.clip import ClipConfig, ClipExtractor, ClipManager, ClipResult
from ..core.highlight import HighlightDetector

router = APIRouter(prefix="/api/clip", tags=["clip"])

# Global instances
_clip_manager: Optional[ClipManager] = None


def get_clip_manager() -> ClipManager:
    """Get or create ClipManager instance."""
    global _clip_manager
    if _clip_manager is None:
        _clip_manager = ClipManager()
    return _clip_manager


# === Request/Response Models ===

class ClipConfigModel(BaseModel):
    """Configuration for clip extraction."""
    pre_buffer_ms: int = Field(default=2000, description="Time before highlight in ms")
    post_buffer_ms: int = Field(default=3000, description="Time after highlight in ms")
    default_format: str = Field(default="mp4", description="Output format (mp4, webm, gif)")
    crf: int = Field(default=23, ge=0, le=51, description="Quality (lower = better)")
    max_clips: int = Field(default=10, description="Maximum clips to extract")


class ExtractClipRequest(BaseModel):
    """Request to extract a single clip."""
    video_path: str = Field(..., description="Path to source video")
    start_ms: int = Field(..., ge=0, description="Start time in milliseconds")
    end_ms: int = Field(..., gt=0, description="End time in milliseconds")
    output_path: Optional[str] = Field(default=None, description="Output path (auto-generated if None)")
    format: Optional[str] = Field(default=None, description="Output format (mp4, webm, gif)")


class ExtractFromHighlightRequest(BaseModel):
    """Request to extract a clip from a highlight."""
    video_path: str = Field(..., description="Path to source video")
    highlight_timestamp_ms: int = Field(..., ge=0, description="Highlight timestamp in ms")
    highlight_duration_ms: int = Field(default=3000, description="Highlight duration in ms")
    highlight_type: str = Field(default="manual_marker", description="Highlight type")
    highlight_label: str = Field(default="Clip", description="Highlight label")
    output_dir: Optional[str] = Field(default=None, description="Output directory")
    format: Optional[str] = Field(default=None, description="Output format")


class AutoClipRequest(BaseModel):
    """Request to auto-detect highlights and extract clips."""
    video_path: str = Field(..., description="Path to source video")
    output_dir: Optional[str] = Field(default=None, description="Output directory")
    session_log_path: Optional[str] = Field(default=None, description="Session log for additional highlight data")
    max_clips: int = Field(default=5, ge=1, le=20, description="Maximum clips to extract")
    create_reel: bool = Field(default=True, description="Also create a highlight reel")


class HighlightReelRequest(BaseModel):
    """Request to create a highlight reel."""
    video_path: str = Field(..., description="Path to source video")
    highlight_timestamps_ms: list[int] = Field(..., description="List of highlight timestamps")
    output_path: Optional[str] = Field(default=None, description="Output path for reel")
    max_clips: Optional[int] = Field(default=None, description="Maximum clips in reel")
    add_transitions: bool = Field(default=True, description="Add fade transitions")


class ClipResultResponse(BaseModel):
    """Response for clip extraction."""
    success: bool
    output_path: Optional[str] = None
    duration_ms: int = 0
    error: Optional[str] = None


class AutoClipResponse(BaseModel):
    """Response for auto-clip extraction."""
    clips: list[dict]
    reel: Optional[str] = None
    highlights_count: int


# === Endpoints ===

@router.get("/status")
async def get_clip_status():
    """Get clip extraction status and capabilities."""
    import shutil
    
    ffmpeg_available = shutil.which("ffmpeg") is not None
    ffprobe_available = shutil.which("ffprobe") is not None
    
    manager = get_clip_manager()
    
    return {
        "status": "ready" if (ffmpeg_available and ffprobe_available) else "missing_dependencies",
        "ffmpeg_available": ffmpeg_available,
        "ffprobe_available": ffprobe_available,
        "config": {
            "pre_buffer_ms": manager.extractor.config.pre_buffer_ms,
            "post_buffer_ms": manager.extractor.config.post_buffer_ms,
            "default_format": manager.extractor.config.default_format,
            "max_clips": manager.extractor.config.max_clips
        }
    }


@router.post("/config")
async def update_clip_config(config: ClipConfigModel):
    """Update clip extraction configuration."""
    manager = get_clip_manager()
    
    manager.extractor.config.pre_buffer_ms = config.pre_buffer_ms
    manager.extractor.config.post_buffer_ms = config.post_buffer_ms
    manager.extractor.config.default_format = config.default_format
    manager.extractor.config.crf = config.crf
    manager.extractor.config.max_clips = config.max_clips
    
    return {"status": "updated", "config": config.model_dump()}


@router.post("/extract", response_model=ClipResultResponse)
async def extract_clip(request: ExtractClipRequest):
    """
    Extract a clip from a video.
    
    Specify start and end times in milliseconds.
    """
    video_path = Path(request.video_path)
    if not video_path.exists():
        raise HTTPException(status_code=404, detail=f"Video not found: {request.video_path}")
    
    manager = get_clip_manager()
    
    result = await manager.extract_time_range(
        video_path=video_path,
        start_ms=request.start_ms,
        end_ms=request.end_ms,
        output_path=Path(request.output_path) if request.output_path else None,
        format=request.format or "mp4"
    )
    
    return ClipResultResponse(
        success=result.success,
        output_path=str(result.output_path) if result.output_path else None,
        duration_ms=result.duration_ms,
        error=result.error
    )


@router.post("/extract-from-highlight", response_model=ClipResultResponse)
async def extract_from_highlight(request: ExtractFromHighlightRequest):
    """
    Extract a clip from a highlight with pre/post buffer.
    
    The clip will include time before and after the highlight based on config.
    """
    from ..core.highlight import Highlight, HighlightType
    
    video_path = Path(request.video_path)
    if not video_path.exists():
        raise HTTPException(status_code=404, detail=f"Video not found: {request.video_path}")
    
    # Create Highlight object
    try:
        highlight_type = HighlightType(request.highlight_type)
    except ValueError:
        highlight_type = HighlightType.MANUAL_MARKER
    
    highlight = Highlight(
        timestamp_ms=request.highlight_timestamp_ms,
        duration_ms=request.highlight_duration_ms,
        highlight_type=highlight_type,
        score=1.0,
        label=request.highlight_label
    )
    
    manager = get_clip_manager()
    
    result = await manager.extractor.extract_from_highlight(
        video_path=video_path,
        highlight=highlight,
        output_dir=Path(request.output_dir) if request.output_dir else None,
        format=request.format
    )
    
    return ClipResultResponse(
        success=result.success,
        output_path=str(result.output_path) if result.output_path else None,
        duration_ms=result.duration_ms,
        error=result.error
    )


@router.post("/auto", response_model=AutoClipResponse)
async def auto_clip_video(request: AutoClipRequest):
    """
    Automatically detect highlights and extract clips.
    
    Analyzes the video for audio spikes, emotion peaks, etc.
    Optionally creates a highlight reel from the best clips.
    """
    video_path = Path(request.video_path)
    if not video_path.exists():
        raise HTTPException(status_code=404, detail=f"Video not found: {request.video_path}")
    
    manager = get_clip_manager()
    
    result = await manager.auto_clip_video(
        video_path=video_path,
        output_dir=Path(request.output_dir) if request.output_dir else None,
        session_log_path=Path(request.session_log_path) if request.session_log_path else None,
        max_clips=request.max_clips,
        create_reel=request.create_reel
    )
    
    return AutoClipResponse(
        clips=result["clips"],
        reel=result["reel"],
        highlights_count=result["highlights_count"]
    )


@router.post("/reel", response_model=ClipResultResponse)
async def create_highlight_reel(request: HighlightReelRequest):
    """
    Create a highlight reel from specified timestamps.
    
    Concatenates clips at the given timestamps into a single video.
    """
    from ..core.highlight import Highlight, HighlightType
    
    video_path = Path(request.video_path)
    if not video_path.exists():
        raise HTTPException(status_code=404, detail=f"Video not found: {request.video_path}")
    
    if not request.highlight_timestamps_ms:
        raise HTTPException(status_code=400, detail="No highlight timestamps provided")
    
    # Create Highlight objects from timestamps
    highlights = [
        Highlight(
            timestamp_ms=ts,
            duration_ms=3000,  # Default 3 seconds
            highlight_type=HighlightType.MANUAL_MARKER,
            score=1.0,
            label=f"Highlight at {ts}ms"
        )
        for ts in request.highlight_timestamps_ms
    ]
    
    manager = get_clip_manager()
    
    result = await manager.extractor.create_highlight_reel(
        video_path=video_path,
        highlights=highlights,
        output_path=Path(request.output_path) if request.output_path else None,
        max_clips=request.max_clips,
        add_transitions=request.add_transitions
    )
    
    return ClipResultResponse(
        success=result.success,
        output_path=str(result.output_path) if result.output_path else None,
        duration_ms=result.duration_ms,
        error=result.error
    )


@router.get("/formats")
async def get_supported_formats():
    """Get list of supported output formats."""
    return {
        "formats": [
            {
                "id": "mp4",
                "name": "MP4 (H.264)",
                "description": "Best compatibility, good quality",
                "extension": ".mp4"
            },
            {
                "id": "webm",
                "name": "WebM (VP9)",
                "description": "Web-optimized, smaller size",
                "extension": ".webm"
            },
            {
                "id": "gif",
                "name": "GIF (Animated)",
                "description": "For short clips, widely supported",
                "extension": ".gif"
            }
        ],
        "default": "mp4"
    }

"""
REST API for Highlight Detection.

Endpoints:
- POST /api/highlight/start - Start highlight detection session
- POST /api/highlight/stop - Stop session and get highlights
- POST /api/highlight/marker - Add manual marker
- POST /api/highlight/analyze - Analyze audio file for highlights
- GET /api/highlight/list - Get current highlights
- GET /api/highlight/top - Get top N highlights
- GET /api/highlight/chapters - Generate YouTube chapters
- POST /api/highlight/export - Export highlights to file
"""

import logging
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..core.highlight import (
    HighlightConfig,
    HighlightDetector,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/highlight", tags=["highlight"])

# Global detector instance (can be replaced per session)
_detector: Optional[HighlightDetector] = None


def get_detector() -> HighlightDetector:
    """Get or create the global detector instance."""
    global _detector
    if _detector is None:
        _detector = HighlightDetector()
    return _detector


# === Request/Response Models ===

class HighlightConfigRequest(BaseModel):
    """Configuration for highlight detection."""
    audio_threshold: float = Field(0.7, ge=0.0, le=1.0, description="RMS threshold for audio spike detection")
    emotion_threshold: float = Field(0.7, ge=0.0, le=1.0, description="Emotion intensity threshold")
    emotion_types: list[str] = Field(default=["excited", "surprised", "happy", "angry"])
    chat_burst_threshold: int = Field(5, ge=1, description="Messages needed for burst detection")
    chat_burst_window_ms: int = Field(5000, ge=1000, description="Time window for burst detection")
    merge_window_ms: int = Field(3000, ge=0, description="Merge highlights within this window")
    highlight_keywords: list[str] = Field(default=[
        "やばい", "すごい", "マジ", "草", "www", "神", "かわいい",
        "amazing", "wow", "omg", "lol", "poggers", "clutch"
    ])


class StartSessionRequest(BaseModel):
    """Request to start highlight detection session."""
    config: Optional[HighlightConfigRequest] = None


class MarkerRequest(BaseModel):
    """Request to add a manual marker."""
    label: str = Field(..., description="Label for the marker")
    timestamp_ms: Optional[int] = Field(None, description="Override timestamp (ms from session start)")


class EmotionEventRequest(BaseModel):
    """Request to process an emotion event."""
    emotion: str = Field(..., description="Emotion type (e.g., excited, happy)")
    intensity: float = Field(..., ge=0.0, le=1.0, description="Emotion intensity")
    timestamp_ms: Optional[int] = None


class ChatMessageRequest(BaseModel):
    """Request to process a chat message."""
    author: str = Field(..., description="Message author")
    text: str = Field(..., description="Message text")
    amount: Optional[float] = Field(None, description="Superchat amount (if applicable)")
    timestamp_ms: Optional[int] = None


class AnalyzeRequest(BaseModel):
    """Request to analyze audio file."""
    audio_path: str = Field(..., description="Path to audio file")
    config: Optional[HighlightConfigRequest] = None


class ExportRequest(BaseModel):
    """Request to export highlights."""
    output_path: str = Field(..., description="Path for output JSON file")


class ChaptersRequest(BaseModel):
    """Request to generate chapters."""
    video_duration_ms: int = Field(..., description="Total video duration in milliseconds")
    max_chapters: int = Field(10, ge=1, le=50, description="Maximum number of chapters")


class HighlightResponse(BaseModel):
    """Single highlight in response."""
    timestamp_ms: int
    timestamp_str: str
    duration_ms: int
    type: str
    score: float
    label: str
    metadata: dict


class HighlightsResponse(BaseModel):
    """Response containing highlights list."""
    total: int
    highlights: list[HighlightResponse]


class ChapterResponse(BaseModel):
    """Single chapter."""
    timestamp_ms: int
    timestamp_str: str
    title: str


class ChaptersResponse(BaseModel):
    """Response containing chapters."""
    total: int
    chapters: list[ChapterResponse]


class StatusResponse(BaseModel):
    """Status response."""
    status: str
    message: str


# === Endpoints ===

@router.post("/start", response_model=StatusResponse)
async def start_session(request: Optional[StartSessionRequest] = None):
    """
    Start a new highlight detection session.

    Clears any existing highlights and begins tracking.
    """
    global _detector

    config = None
    if request and request.config:
        config = HighlightConfig(
            audio_threshold=request.config.audio_threshold,
            emotion_threshold=request.config.emotion_threshold,
            emotion_types=request.config.emotion_types,
            chat_burst_threshold=request.config.chat_burst_threshold,
            chat_burst_window_ms=request.config.chat_burst_window_ms,
            merge_window_ms=request.config.merge_window_ms,
            highlight_keywords=request.config.highlight_keywords,
        )

    _detector = HighlightDetector(config)
    _detector.start_session()

    logger.info("Highlight detection session started")
    return StatusResponse(status="ok", message="Highlight detection session started")


@router.post("/stop", response_model=HighlightsResponse)
async def stop_session():
    """
    Stop the current highlight detection session.

    Returns all detected highlights, merged and sorted.
    """
    detector = get_detector()
    highlights = detector.stop_session()

    return HighlightsResponse(
        total=len(highlights),
        highlights=[
            HighlightResponse(
                timestamp_ms=h.timestamp_ms,
                timestamp_str=h.timestamp_str,
                duration_ms=h.duration_ms,
                type=h.highlight_type.value,
                score=h.score,
                label=h.label,
                metadata=h.metadata
            )
            for h in highlights
        ]
    )


@router.post("/marker", response_model=StatusResponse)
async def add_marker(request: MarkerRequest):
    """
    Add a manual highlight marker.

    Useful for marking important moments during recording/streaming.
    """
    detector = get_detector()
    detector.add_manual_marker(request.label, request.timestamp_ms)

    return StatusResponse(status="ok", message=f"Marker added: {request.label}")


@router.post("/emotion", response_model=StatusResponse)
async def process_emotion(request: EmotionEventRequest):
    """
    Process an emotion event for highlight detection.
    """
    detector = get_detector()
    detector.process_emotion(request.emotion, request.intensity, request.timestamp_ms)

    return StatusResponse(status="ok", message=f"Emotion processed: {request.emotion}")


@router.post("/chat", response_model=StatusResponse)
async def process_chat(request: ChatMessageRequest):
    """
    Process a chat message for highlight detection.

    Detects superchats, keywords, and chat bursts.
    """
    detector = get_detector()
    message = {
        "author": request.author,
        "text": request.text,
    }
    if request.amount:
        message["amount"] = request.amount

    detector.process_chat_message(message, request.timestamp_ms)

    return StatusResponse(status="ok", message="Chat message processed")


@router.get("/list", response_model=HighlightsResponse)
async def list_highlights():
    """
    Get all current highlights (unmerged).
    """
    detector = get_detector()

    return HighlightsResponse(
        total=len(detector.highlights),
        highlights=[
            HighlightResponse(
                timestamp_ms=h.timestamp_ms,
                timestamp_str=h.timestamp_str,
                duration_ms=h.duration_ms,
                type=h.highlight_type.value,
                score=h.score,
                label=h.label,
                metadata=h.metadata
            )
            for h in detector.highlights
        ]
    )


@router.get("/top", response_model=HighlightsResponse)
async def get_top_highlights(n: int = 10):
    """
    Get top N highlights by weighted score.
    """
    detector = get_detector()
    top = detector.get_top_highlights(n)

    return HighlightsResponse(
        total=len(top),
        highlights=[
            HighlightResponse(
                timestamp_ms=h.timestamp_ms,
                timestamp_str=h.timestamp_str,
                duration_ms=h.duration_ms,
                type=h.highlight_type.value,
                score=h.score,
                label=h.label,
                metadata=h.metadata
            )
            for h in top
        ]
    )


@router.post("/chapters", response_model=ChaptersResponse)
async def generate_chapters(request: ChaptersRequest):
    """
    Generate YouTube-style chapters from highlights.
    """
    detector = get_detector()
    chapters = detector.generate_chapters(request.video_duration_ms, request.max_chapters)

    # Format timestamps
    def format_timestamp(ms: int) -> str:
        total_seconds = ms / 1000
        hours = int(total_seconds // 3600)
        minutes = int((total_seconds % 3600) // 60)
        seconds = total_seconds % 60
        return f"{hours:02d}:{minutes:02d}:{seconds:06.3f}"

    return ChaptersResponse(
        total=len(chapters),
        chapters=[
            ChapterResponse(
                timestamp_ms=c["timestamp_ms"],
                timestamp_str=format_timestamp(c["timestamp_ms"]),
                title=c["title"]
            )
            for c in chapters
        ]
    )


@router.post("/analyze", response_model=HighlightsResponse)
async def analyze_audio(request: AnalyzeRequest):
    """
    Analyze an audio file for highlights (post-recording analysis).
    """
    audio_path = Path(request.audio_path)
    if not audio_path.exists():
        raise HTTPException(status_code=404, detail=f"Audio file not found: {audio_path}")

    config = None
    if request.config:
        config = HighlightConfig(
            audio_threshold=request.config.audio_threshold,
            emotion_threshold=request.config.emotion_threshold,
        )

    detector = HighlightDetector(config)
    highlights = await detector.analyze_audio_file(audio_path)

    return HighlightsResponse(
        total=len(highlights),
        highlights=[
            HighlightResponse(
                timestamp_ms=h.timestamp_ms,
                timestamp_str=h.timestamp_str,
                duration_ms=h.duration_ms,
                type=h.highlight_type.value,
                score=h.score,
                label=h.label,
                metadata=h.metadata
            )
            for h in highlights
        ]
    )


@router.post("/export", response_model=StatusResponse)
async def export_highlights(request: ExportRequest):
    """
    Export current highlights to a JSON file.
    """
    detector = get_detector()
    output_path = Path(request.output_path)

    try:
        detector.export_highlights(output_path)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Export failed: {e}")

    return StatusResponse(status="ok", message=f"Highlights exported to {output_path}")

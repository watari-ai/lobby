"""
Recording API Routes for Lobby

Provides REST endpoints for the recording pipeline:
- Script upload/parse
- Recording session management (start/stop/status)
- Video generation with lipsync
"""

import asyncio
import uuid
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..core.avatar import AvatarParts, LipsyncConfig
from ..core.pipeline import PipelineConfig, RecordingPipeline
from ..core.tts import TTSConfig
from ..core.video import VideoConfig
from ..modes.recording import Script

router = APIRouter(prefix="/recording", tags=["recording"])


# --- Models ---


class TTSSettings(BaseModel):
    """TTS settings for recording."""
    provider: str = Field("miotts", description="TTS provider (miotts, qwen3-tts, openai)")
    base_url: str = Field("http://localhost:8001", description="TTS API base URL")
    voice: str = Field("lobby", description="Voice name/preset")


class AvatarSettings(BaseModel):
    """Avatar parts paths for PNG lipsync."""
    base: str = Field(..., description="Base body image path")
    mouth_closed: str = Field(..., description="Closed mouth image path")
    mouth_open_s: Optional[str] = Field(None, description="Small open mouth")
    mouth_open_m: Optional[str] = Field(None, description="Medium open mouth")
    mouth_open_l: Optional[str] = Field(None, description="Large open mouth")
    eyes_open: Optional[str] = Field(None, description="Open eyes")
    eyes_closed: Optional[str] = Field(None, description="Closed eyes (blink)")


class VideoSettings(BaseModel):
    """Video output settings."""
    fps: int = Field(30, ge=1, le=60)
    width: int = Field(1920, ge=320)
    height: int = Field(1080, ge=240)
    crf: int = Field(23, ge=0, le=51)


class RecordingRequest(BaseModel):
    """Request to start a recording session."""
    script_text: Optional[str] = Field(None, description="Script as plain text")
    script_json: Optional[str] = Field(None, description="Script as JSON string")
    script_path: Optional[str] = Field(None, description="Path to script file on server")
    tts: TTSSettings = Field(default_factory=TTSSettings)
    avatar: AvatarSettings
    video: VideoSettings = Field(default_factory=VideoSettings)
    background_image: Optional[str] = Field(None, description="Background image path")
    output_dir: str = Field("./output", description="Output directory")


class RecordingStatus(BaseModel):
    """Recording session status."""
    session_id: str
    status: str  # "pending", "running", "completed", "failed"
    progress_current: int = 0
    progress_total: int = 0
    progress_message: str = ""
    output_path: Optional[str] = None
    error: Optional[str] = None


class ScriptInfo(BaseModel):
    """Parsed script information."""
    title: str
    line_count: int
    lines: list[dict]


# --- Session Storage ---

_sessions: dict[str, RecordingStatus] = {}
_tasks: dict[str, asyncio.Task] = {}


# --- Helpers ---


def _parse_script(req: RecordingRequest) -> Script:
    """Parse script from request."""
    if req.script_path:
        path = Path(req.script_path)
        if not path.exists():
            raise HTTPException(404, f"Script file not found: {req.script_path}")
        return Script.from_file(path)
    elif req.script_json:
        return Script.from_json(req.script_json)
    elif req.script_text:
        return Script.from_text(req.script_text)
    else:
        raise HTTPException(400, "Provide script_text, script_json, or script_path")


def _build_avatar_parts(settings: AvatarSettings) -> AvatarParts:
    """Build AvatarParts from settings."""
    return AvatarParts(
        base=Path(settings.base),
        mouth_closed=Path(settings.mouth_closed),
        mouth_open_s=Path(settings.mouth_open_s) if settings.mouth_open_s else None,
        mouth_open_m=Path(settings.mouth_open_m) if settings.mouth_open_m else None,
        mouth_open_l=Path(settings.mouth_open_l) if settings.mouth_open_l else None,
        eyes_open=Path(settings.eyes_open) if settings.eyes_open else None,
        eyes_closed=Path(settings.eyes_closed) if settings.eyes_closed else None,
    )


async def _run_recording(session_id: str, req: RecordingRequest):
    """Background task for recording pipeline."""
    session = _sessions[session_id]

    try:
        script = _parse_script(req)
        session.progress_total = len(script.lines)
        session.status = "running"

        avatar_parts = _build_avatar_parts(req.avatar)

        config = PipelineConfig(
            tts=TTSConfig(
                provider=req.tts.provider,
                base_url=req.tts.base_url,
                voice=req.tts.voice,
            ),
            lipsync=LipsyncConfig(fps=req.video.fps),
            video=VideoConfig(
                fps=req.video.fps,
                width=req.video.width,
                height=req.video.height,
                crf=req.video.crf,
            ),
            avatar_parts=avatar_parts,
            output_dir=Path(req.output_dir),
            background_image=Path(req.background_image) if req.background_image else None,
        )

        def on_progress(current: int, total: int, status: str):
            session.progress_current = current
            session.progress_total = total
            session.progress_message = status

        async with RecordingPipeline(config) as pipeline:
            output_path = await pipeline.process_script(script, on_progress)

        session.status = "completed"
        session.output_path = str(output_path)

    except Exception as e:
        session.status = "failed"
        session.error = str(e)


# --- Routes ---


@router.post("/parse-script", response_model=ScriptInfo)
async def parse_script(
    script_text: Optional[str] = None,
    script_path: Optional[str] = None,
):
    """Parse a script and return its structure (preview without recording)."""
    if script_path:
        path = Path(script_path)
        if not path.exists():
            raise HTTPException(404, f"Script file not found: {script_path}")
        script = Script.from_file(path)
    elif script_text:
        script = Script.from_text(script_text)
    else:
        raise HTTPException(400, "Provide script_text or script_path")

    return ScriptInfo(
        title=script.title,
        line_count=len(script.lines),
        lines=[
            {
                "text": line.text,
                "emotion": line.emotion.value,
                "wait_after": line.wait_after,
                "gesture": line.gesture,
            }
            for line in script.lines
        ],
    )


@router.post("/start", response_model=RecordingStatus)
async def start_recording(req: RecordingRequest):
    """Start a recording session (async). Returns session ID to poll status."""
    # Validate script can be parsed
    _parse_script(req)

    session_id = str(uuid.uuid4())[:8]
    session = RecordingStatus(
        session_id=session_id,
        status="pending",
    )
    _sessions[session_id] = session

    task = asyncio.create_task(_run_recording(session_id, req))
    _tasks[session_id] = task

    return session


@router.get("/status/{session_id}", response_model=RecordingStatus)
async def get_recording_status(session_id: str):
    """Get the status of a recording session."""
    if session_id not in _sessions:
        raise HTTPException(404, f"Session not found: {session_id}")
    return _sessions[session_id]


@router.post("/cancel/{session_id}")
async def cancel_recording(session_id: str):
    """Cancel a running recording session."""
    if session_id not in _sessions:
        raise HTTPException(404, f"Session not found: {session_id}")

    if session_id in _tasks:
        _tasks[session_id].cancel()
        del _tasks[session_id]

    _sessions[session_id].status = "cancelled"
    return {"message": f"Session {session_id} cancelled"}


@router.get("/sessions", response_model=list[RecordingStatus])
async def list_sessions():
    """List all recording sessions."""
    return list(_sessions.values())


@router.delete("/sessions/{session_id}")
async def delete_session(session_id: str):
    """Delete a recording session from history."""
    if session_id not in _sessions:
        raise HTTPException(404, f"Session not found: {session_id}")

    if session_id in _tasks:
        _tasks[session_id].cancel()
        del _tasks[session_id]

    del _sessions[session_id]
    return {"message": f"Session {session_id} deleted"}

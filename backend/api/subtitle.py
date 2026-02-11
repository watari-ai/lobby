"""Subtitle API - リアルタイム字幕WebSocket + REST API"""

import asyncio
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException
from pydantic import BaseModel
from loguru import logger

from ..core.live_subtitle import (
    LiveSubtitleManager,
    SubtitleBroadcaster,
    SubtitleConfig,
    LiveSubtitle,
    SubtitleStyle,
    subtitle_broadcaster,
)

router = APIRouter()


# --- Pydantic Models ---

class ShowSubtitleRequest(BaseModel):
    """字幕表示リクエスト"""
    text: str
    speaker: str = ""
    emotion: str = "neutral"
    duration_ms: Optional[int] = None


class SubtitleResponse(BaseModel):
    """字幕レスポンス"""
    id: str
    text: str
    speaker: str
    style: str
    emotion: str
    duration_ms: int


class ExportRequest(BaseModel):
    """エクスポートリクエスト"""
    format: str = "srt"  # "srt" or "vtt"


# --- WebSocket Endpoint ---

@router.websocket("/ws/subtitle")
async def websocket_subtitle(websocket: WebSocket):
    """リアルタイム字幕WebSocket

    接続後、以下のメッセージを受信:
    - {"type": "subtitle", "action": "show", "data": {...}}
    - {"type": "subtitle", "action": "clear"}

    クライアントから送信可能:
    - {"action": "show", "text": "...", "speaker": "...", "emotion": "..."}
    - {"action": "clear"}
    - {"action": "get_current"}
    - {"action": "get_history", "limit": 10}
    - {"action": "export", "format": "srt"}
    """
    await websocket.accept()
    subtitle_broadcaster.add_connection(websocket)

    # 現在の字幕があれば送信
    current = subtitle_broadcaster.manager.current
    if current:
        await websocket.send_json({
            "type": "subtitle",
            "action": "show",
            "data": current.to_dict(),
        })

    try:
        while True:
            data = await websocket.receive_json()
            action = data.get("action")

            if action == "show":
                # 字幕を表示
                text = data.get("text", "")
                if text:
                    subtitle = await subtitle_broadcaster.manager.show_subtitle(
                        text=text,
                        speaker=data.get("speaker", ""),
                        emotion=data.get("emotion", "neutral"),
                        duration_ms=data.get("duration_ms"),
                    )
                    await websocket.send_json({
                        "type": "response",
                        "action": "show",
                        "success": True,
                        "subtitle_id": subtitle.id,
                    })

            elif action == "clear":
                # 字幕をクリア
                await subtitle_broadcaster.manager.clear_subtitle()
                await websocket.send_json({
                    "type": "response",
                    "action": "clear",
                    "success": True,
                })

            elif action == "get_current":
                # 現在の字幕を取得
                current = subtitle_broadcaster.manager.current
                await websocket.send_json({
                    "type": "response",
                    "action": "get_current",
                    "data": current.to_dict() if current else None,
                })

            elif action == "get_history":
                # 履歴を取得
                limit = data.get("limit", 50)
                history = subtitle_broadcaster.manager.history[-limit:]
                await websocket.send_json({
                    "type": "response",
                    "action": "get_history",
                    "data": [s.to_dict() for s in history],
                })

            elif action == "export":
                # 履歴をエクスポート
                format = data.get("format", "srt")
                content = subtitle_broadcaster.manager.export_history(format)
                await websocket.send_json({
                    "type": "response",
                    "action": "export",
                    "format": format,
                    "content": content,
                })

    except WebSocketDisconnect:
        subtitle_broadcaster.remove_connection(websocket)
        logger.debug("Subtitle WebSocket disconnected")


# --- REST Endpoints ---

@router.post("/api/subtitle/show", response_model=SubtitleResponse)
async def show_subtitle(request: ShowSubtitleRequest):
    """字幕を表示

    Args:
        request: 表示リクエスト

    Returns:
        表示された字幕情報
    """
    subtitle = await subtitle_broadcaster.manager.show_subtitle(
        text=request.text,
        speaker=request.speaker,
        emotion=request.emotion,
        duration_ms=request.duration_ms,
    )

    return SubtitleResponse(
        id=subtitle.id,
        text=subtitle.text,
        speaker=subtitle.speaker,
        style=subtitle.style.value,
        emotion=subtitle.emotion,
        duration_ms=subtitle.duration_ms,
    )


@router.post("/api/subtitle/clear")
async def clear_subtitle():
    """字幕をクリア"""
    await subtitle_broadcaster.manager.clear_subtitle()
    return {"status": "cleared"}


@router.get("/api/subtitle/current")
async def get_current_subtitle():
    """現在の字幕を取得"""
    current = subtitle_broadcaster.manager.current
    if current:
        return {"subtitle": current.to_dict()}
    return {"subtitle": None}


@router.get("/api/subtitle/history")
async def get_subtitle_history(limit: int = 50):
    """字幕履歴を取得

    Args:
        limit: 取得する最大件数

    Returns:
        字幕履歴リスト
    """
    history = subtitle_broadcaster.manager.history[-limit:]
    return {
        "history": [s.to_dict() for s in history],
        "count": len(history),
    }


@router.post("/api/subtitle/export")
async def export_subtitle_history(request: ExportRequest):
    """字幕履歴をエクスポート

    Args:
        request: エクスポートリクエスト（format: "srt" or "vtt"）

    Returns:
        字幕ファイル内容
    """
    format = request.format.lower()
    if format not in ["srt", "vtt"]:
        raise HTTPException(status_code=400, detail="Format must be 'srt' or 'vtt'")

    content = subtitle_broadcaster.manager.export_history(format)
    return {
        "format": format,
        "content": content,
        "entry_count": len(subtitle_broadcaster.manager.history),
    }


@router.delete("/api/subtitle/history")
async def clear_subtitle_history():
    """字幕履歴をクリア"""
    subtitle_broadcaster.manager.clear_history()
    return {"status": "history_cleared"}


@router.get("/api/subtitle/styles")
async def get_subtitle_styles():
    """利用可能な字幕スタイル一覧"""
    return {
        "styles": [s.value for s in SubtitleStyle],
        "emotion_mapping": {
            "happy": "normal",
            "excited": "excited",
            "sad": "sad",
            "angry": "angry",
            "fear": "whisper",
            "surprise": "excited",
            "neutral": "normal",
        },
    }

"""Live Mode API - ライブ配信制御エンドポイント"""

import asyncio
import base64
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException
from loguru import logger
from pydantic import BaseModel

from ..modes.live import (
    LiveMode,
    LiveModeConfig,
    LiveInput,
    LiveOutput,
    InputSource,
    create_lobby_live_mode,
)
from ..core.openclaw import OpenClawConfig, LOBBY_SYSTEM_PROMPT
from ..core.tts import TTSConfig

router = APIRouter(prefix="/api/live", tags=["live"])


# グローバルライブモードインスタンス
_live_mode: Optional[LiveMode] = None
_output_websockets: list[WebSocket] = []


# === リクエスト/レスポンスモデル ===

class LiveStartRequest(BaseModel):
    """ライブモード開始リクエスト"""
    gateway_url: str = "http://localhost:18789"
    tts_url: str = "http://localhost:8001"
    tts_voice: str = "lobby"
    system_prompt: Optional[str] = None


class LiveInputRequest(BaseModel):
    """入力追加リクエスト"""
    text: str
    source: str = "manual"  # youtube, twitch, microphone, manual
    author: str = "Anonymous"
    author_id: str = ""
    metadata: dict = {}


class LiveChatRequest(BaseModel):
    """単発チャットリクエスト"""
    text: str
    author: str = "User"


class LiveStatusResponse(BaseModel):
    """ステータスレスポンス"""
    running: bool
    queue_size: int
    gateway_url: Optional[str] = None


# === エンドポイント ===

@router.get("/status", response_model=LiveStatusResponse)
async def get_status():
    """ライブモードのステータス取得"""
    global _live_mode
    
    if _live_mode is None:
        return LiveStatusResponse(running=False, queue_size=0)
    
    return LiveStatusResponse(
        running=_live_mode.is_running,
        queue_size=_live_mode.queue_size,
        gateway_url=_live_mode.config.openclaw.base_url,
    )


@router.post("/start")
async def start_live_mode(request: LiveStartRequest):
    """ライブモード開始"""
    global _live_mode
    
    if _live_mode is not None and _live_mode.is_running:
        raise HTTPException(400, "Live mode already running")
    
    # 設定作成
    config = LiveModeConfig(
        openclaw=OpenClawConfig(
            base_url=request.gateway_url,
            system_prompt=request.system_prompt or LOBBY_SYSTEM_PROMPT,
            temperature=0.9,
            max_tokens=200,
        ),
        tts=TTSConfig(
            base_url=request.tts_url,
            voice=request.tts_voice,
        ),
    )
    
    # ライブモード作成・開始
    _live_mode = LiveMode(config)
    
    # 出力コールバック設定
    def on_output(output: LiveOutput):
        asyncio.create_task(_broadcast_output(output))
    
    _live_mode.set_output_callback(on_output)
    
    await _live_mode.start()
    
    logger.info("Live mode started")
    return {"status": "started", "gateway_url": request.gateway_url}


@router.post("/stop")
async def stop_live_mode():
    """ライブモード停止"""
    global _live_mode
    
    if _live_mode is None:
        raise HTTPException(400, "Live mode not running")
    
    await _live_mode.close()
    _live_mode = None
    
    logger.info("Live mode stopped")
    return {"status": "stopped"}


@router.post("/input")
async def add_input(request: LiveInputRequest):
    """入力をキューに追加"""
    global _live_mode
    
    if _live_mode is None or not _live_mode.is_running:
        raise HTTPException(400, "Live mode not running")
    
    # ソース変換
    source_map = {
        "youtube": InputSource.YOUTUBE_COMMENT,
        "twitch": InputSource.TWITCH_COMMENT,
        "microphone": InputSource.MICROPHONE,
        "manual": InputSource.MANUAL,
    }
    source = source_map.get(request.source.lower(), InputSource.MANUAL)
    
    # 入力作成
    input_data = LiveInput(
        text=request.text,
        source=source,
        author=request.author,
        author_id=request.author_id,
        metadata=request.metadata,
    )
    
    # キューに追加
    added = _live_mode.add_input(input_data)
    
    if not added:
        return {"status": "filtered", "queue_size": _live_mode.queue_size}
    
    return {"status": "queued", "queue_size": _live_mode.queue_size}


@router.post("/chat")
async def chat_single(request: LiveChatRequest):
    """単発チャット（即座に応答を返す）"""
    global _live_mode
    
    if _live_mode is None:
        # ライブモードが起動していない場合は一時的に作成
        _live_mode = await create_lobby_live_mode()
    
    # 単発処理
    output = await _live_mode.process_single(request.text, request.author)
    
    # 音声をBase64エンコード（オプション）
    audio_base64 = None
    if output.audio_path and output.audio_path.exists():
        audio_base64 = base64.b64encode(output.audio_path.read_bytes()).decode()
    
    return {
        "response_text": output.response_text,
        "emotion": {
            "primary": output.emotion.primary.value,
            "secondary": output.emotion.secondary.value if output.emotion.secondary else None,
            "intensity": output.emotion.intensity,
        },
        "audio_base64": audio_base64,
        "live2d_params_count": len(output.live2d_params) if output.live2d_params else 0,
    }


@router.post("/system-prompt")
async def set_system_prompt(prompt: str):
    """システムプロンプト変更"""
    global _live_mode
    
    if _live_mode is None:
        raise HTTPException(400, "Live mode not initialized")
    
    _live_mode.set_system_prompt(prompt)
    return {"status": "updated", "prompt_length": len(prompt)}


@router.websocket("/ws/output")
async def websocket_output(websocket: WebSocket):
    """ライブ出力ストリーミングWebSocket
    
    ライブモードで生成された出力をリアルタイム受信
    
    受信メッセージフォーマット:
    {
        "type": "output",
        "input": {
            "text": "コメント",
            "source": "youtube",
            "author": "視聴者名"
        },
        "response_text": "AI応答",
        "emotion": {
            "primary": "happy",
            "intensity": 0.8
        },
        "audio_path": "/path/to/audio.mp3",
        "has_live2d": true
    }
    """
    await websocket.accept()
    _output_websockets.append(websocket)
    logger.info(f"Live output WebSocket connected. Total: {len(_output_websockets)}")
    
    try:
        while True:
            # クライアントからのメッセージ（keepalive等）
            data = await websocket.receive_json()
            action = data.get("action")
            
            if action == "ping":
                await websocket.send_json({"type": "pong"})
    
    except WebSocketDisconnect:
        if websocket in _output_websockets:
            _output_websockets.remove(websocket)
        logger.info(f"Live output WebSocket disconnected. Total: {len(_output_websockets)}")


async def _broadcast_output(output: LiveOutput):
    """出力をWebSocketにブロードキャスト"""
    message = {
        "type": "output",
        "input": {
            "text": output.input.text,
            "source": output.input.source.value,
            "author": output.input.author,
        },
        "response_text": output.response_text,
        "emotion": {
            "primary": output.emotion.primary.value,
            "secondary": output.emotion.secondary.value if output.emotion.secondary else None,
            "intensity": output.emotion.intensity,
        },
        "audio_path": str(output.audio_path) if output.audio_path else None,
        "has_live2d": output.live2d_params is not None,
    }
    
    disconnected = []
    for ws in _output_websockets:
        try:
            await ws.send_json(message)
        except Exception:
            disconnected.append(ws)
    
    for ws in disconnected:
        if ws in _output_websockets:
            _output_websockets.remove(ws)

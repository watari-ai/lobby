"""Subtitle API - リアルタイム字幕WebSocket + REST API + 翻訳"""

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
from ..core.subtitle_translator import (
    SubtitleTranslator,
    TranslatorConfig,
    TranslationProvider,
    LANGUAGE_NAMES,
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


# --- Translation Endpoints ---

class TranslateTextRequest(BaseModel):
    """テキスト翻訳リクエスト"""
    text: str
    source_lang: str = "ja"
    target_lang: str = "en"
    context: Optional[list[str]] = None


class TranslateHistoryRequest(BaseModel):
    """履歴翻訳リクエスト"""
    target_lang: str = "en"
    source_lang: str = "ja"


class TranslatorConfigRequest(BaseModel):
    """翻訳設定リクエスト"""
    provider: str = "openclaw"
    openclaw_url: str = "http://localhost:18789"
    deepl_api_key: Optional[str] = None
    batch_size: int = 10
    context_lines: int = 2
    formal: bool = False


# グローバル翻訳器インスタンス
_translator: Optional[SubtitleTranslator] = None


def get_translator(config: Optional[TranslatorConfigRequest] = None) -> SubtitleTranslator:
    """翻訳器インスタンス取得"""
    global _translator
    if _translator is None or config is not None:
        translator_config = TranslatorConfig(
            provider=TranslationProvider(config.provider) if config else TranslationProvider.OPENCLAW,
            openclaw_url=config.openclaw_url if config else "http://localhost:18789",
            deepl_api_key=config.deepl_api_key if config else "",
            batch_size=config.batch_size if config else 10,
            context_lines=config.context_lines if config else 2,
            formal=config.formal if config else False,
        )
        _translator = SubtitleTranslator(translator_config)
    return _translator


@router.get("/api/subtitle/translate/languages")
async def get_supported_languages():
    """サポートされている言語一覧"""
    return {
        "languages": LANGUAGE_NAMES,
        "default_source": "ja",
        "default_target": "en",
    }


@router.post("/api/subtitle/translate/text")
async def translate_text(request: TranslateTextRequest):
    """テキストを翻訳

    Args:
        request: 翻訳リクエスト

    Returns:
        翻訳結果
    """
    translator = get_translator()
    
    result = await translator.translate_text(
        text=request.text,
        source_lang=request.source_lang,
        target_lang=request.target_lang,
        context=request.context,
    )
    
    return {
        "original": result.original,
        "translated": result.translated,
        "source_lang": result.source_lang,
        "target_lang": result.target_lang,
        "confidence": result.confidence,
    }


@router.post("/api/subtitle/translate/history")
async def translate_history(request: TranslateHistoryRequest):
    """字幕履歴を翻訳

    現在の履歴を指定言語に翻訳して返す。

    Args:
        request: 翻訳リクエスト

    Returns:
        翻訳された履歴
    """
    history = subtitle_broadcaster.manager.history
    if not history:
        return {
            "translated": [],
            "count": 0,
            "target_lang": request.target_lang,
        }
    
    translator = get_translator()
    
    # テキストを抽出
    texts = [s.text for s in history]
    
    # バッチ翻訳
    translations = await translator.translate_batch(
        texts=texts,
        source_lang=request.source_lang,
        target_lang=request.target_lang,
    )
    
    # 結果を構築
    translated_history = []
    for i, subtitle in enumerate(history):
        translated_history.append({
            "id": subtitle.id,
            "original": subtitle.text,
            "translated": translations[i].translated,
            "speaker": subtitle.speaker,
            "start_time": subtitle.start_time,
            "end_time": subtitle.end_time,
            "confidence": translations[i].confidence,
        })
    
    return {
        "translated": translated_history,
        "count": len(translated_history),
        "source_lang": request.source_lang,
        "target_lang": request.target_lang,
    }


@router.post("/api/subtitle/translate/export")
async def export_translated_subtitles(
    target_lang: str = "en",
    source_lang: str = "ja",
    format: str = "srt",
):
    """字幕履歴を翻訳してエクスポート

    Args:
        target_lang: 翻訳先言語
        source_lang: 元言語
        format: 出力フォーマット（srt/vtt）

    Returns:
        翻訳された字幕ファイル内容
    """
    from ..core.subtitle import SubtitleTrack, SubtitleFormat
    
    history = subtitle_broadcaster.manager.history
    if not history:
        raise HTTPException(status_code=400, detail="No subtitle history")
    
    translator = get_translator()
    
    # 元のトラックを作成
    track = SubtitleTrack(language=source_lang)
    
    for subtitle in history:
        # LiveSubtitleのタイムスタンプをミリ秒に変換
        start_ms = int(subtitle.start_time * 1000) if subtitle.start_time else 0
        end_ms = int(subtitle.end_time * 1000) if subtitle.end_time else start_ms + subtitle.duration_ms
        
        track.add_entry(
            text=subtitle.text,
            start_ms=start_ms,
            end_ms=end_ms,
            speaker=subtitle.speaker,
        )
    
    # 翻訳
    translated_track = await translator.translate_track(track, target_lang)
    
    # エクスポート
    fmt = SubtitleFormat.VTT if format.lower() == "vtt" else SubtitleFormat.SRT
    if fmt == SubtitleFormat.VTT:
        content = translated_track.to_vtt()
    else:
        content = translated_track.to_srt()
    
    return {
        "format": format,
        "target_lang": target_lang,
        "content": content,
        "entry_count": len(translated_track.entries),
    }


@router.post("/api/subtitle/translate/config")
async def configure_translator(config: TranslatorConfigRequest):
    """翻訳器の設定を更新

    Args:
        config: 翻訳設定

    Returns:
        更新結果
    """
    global _translator
    
    # 既存の翻訳器をクローズ
    if _translator:
        await _translator.close()
    
    # 新しい設定で再作成
    _translator = get_translator(config)
    
    return {
        "status": "configured",
        "provider": config.provider,
        "openclaw_url": config.openclaw_url,
        "batch_size": config.batch_size,
    }

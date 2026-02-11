"""WebSocket API for Live2D real-time parameter streaming"""

import asyncio
import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from loguru import logger

from ..core.live2d import (
    EmotionDrivenLive2D,
    Live2DConfig,
    Live2DExpression,
    Live2DFrame,
    Live2DLipsyncAnalyzer,
    Live2DModel,
    Live2DParameters,
)

router = APIRouter()


class ConnectionManager:
    """WebSocket接続管理"""

    def __init__(self):
        self.active_connections: list[WebSocket] = []
        self.current_params: Live2DParameters = Live2DParameters()
        self._streaming: bool = False
        self._stream_task: asyncio.Task | None = None

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"WebSocket connected. Total: {len(self.active_connections)}")

        # 初回パラメータ送信
        await self.send_parameters(websocket, self.current_params)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            logger.info(f"WebSocket disconnected. Total: {len(self.active_connections)}")

    async def send_parameters(
        self,
        websocket: WebSocket,
        params: Live2DParameters,
    ):
        """単一接続にパラメータ送信"""
        message = {
            "type": "parameters",
            "data": params.to_dict(),
        }
        await websocket.send_json(message)

    async def broadcast_parameters(self, params: Live2DParameters):
        """全接続にパラメータをブロードキャスト"""
        self.current_params = params
        message = {
            "type": "parameters",
            "data": params.to_dict(),
        }

        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception:
                disconnected.append(connection)

        for conn in disconnected:
            self.disconnect(conn)

    async def broadcast_frame(self, frame: Live2DFrame):
        """フレームデータをブロードキャスト"""
        message = {
            "type": "frame",
            "timestamp_ms": frame.timestamp_ms,
            "parameters": frame.parameters.to_dict(),
            "expression": frame.expression.value,
            "motion": frame.motion,
        }

        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception:
                disconnected.append(connection)

        for conn in disconnected:
            self.disconnect(conn)

    async def stream_frames(
        self,
        frames: list[Live2DFrame],
        speed: float = 1.0,
    ):
        """フレームシーケンスをリアルタイムストリーム"""
        if not frames:
            return

        self._streaming = True
        prev_timestamp = 0

        try:
            for frame in frames:
                if not self._streaming:
                    break

                # フレーム間の待機時間を計算
                wait_ms = (frame.timestamp_ms - prev_timestamp) / speed
                if wait_ms > 0:
                    await asyncio.sleep(wait_ms / 1000)

                await self.broadcast_frame(frame)
                prev_timestamp = frame.timestamp_ms

        finally:
            self._streaming = False

    def stop_streaming(self):
        """ストリーミング停止"""
        self._streaming = False


# グローバル接続マネージャー
manager = ConnectionManager()

# 感情エンジン統合インスタンス
emotion_driven = EmotionDrivenLive2D()


@router.websocket("/ws/live2d")
async def websocket_live2d(websocket: WebSocket):
    """Live2Dパラメータストリーミング用WebSocket

    接続後、以下のメッセージタイプを受信:
    - parameters: パラメータ更新 {"type": "parameters", "data": {...}}
    - frame: フレーム更新 {"type": "frame", "timestamp_ms": int, "parameters": {...}, ...}
    - emotion: 感情分析結果 {"type": "emotion", "expression": "happy", "intensity": 0.8}

    クライアントから送信可能:
    - {"action": "set_expression", "expression": "happy"}
    - {"action": "play_motion", "motion": "idle_01"}
    - {"action": "set_param", "name": "ParamMouthOpenY", "value": 0.5}
    - {"action": "analyze_text", "text": "すごいっす！"} # テキストから感情分析
    - {"action": "speak", "text": "すごいっす！", "audio_path": "/path/to/audio.mp3"} # 感情+リップシンク
    """
    await manager.connect(websocket)

    try:
        while True:
            data = await websocket.receive_json()
            action = data.get("action")

            if action == "set_expression":
                # 表情変更
                expr_name = data.get("expression", "neutral")
                try:
                    expression = Live2DExpression(expr_name)
                    # 表情プリセットからパラメータを生成
                    config = Live2DConfig()
                    preset = config.expression_presets.get(expression, {})
                    params = Live2DParameters(**preset)
                    await manager.broadcast_parameters(params)
                except ValueError:
                    await websocket.send_json({
                        "type": "error",
                        "message": f"Unknown expression: {expr_name}",
                    })

            elif action == "set_param":
                # 個別パラメータ変更
                name = data.get("name")
                value = data.get("value", 0.0)

                # パラメータ名をPython属性名に変換
                param_attr = name.replace("Param", "param_").lower()
                if hasattr(manager.current_params, param_attr):
                    setattr(manager.current_params, param_attr, value)
                    await manager.broadcast_parameters(manager.current_params)

            elif action == "play_motion":
                # モーション再生（フロントエンド側で処理）
                motion = data.get("motion")
                for conn in manager.active_connections:
                    await conn.send_json({
                        "type": "motion",
                        "motion": motion,
                    })

            elif action == "stop":
                manager.stop_streaming()

            elif action == "analyze_text":
                # テキストから感情分析（表情のみ更新、リップシンクなし）
                text = data.get("text", "")
                if text:
                    expression, params = emotion_driven.get_expression_params(text)
                    await manager.broadcast_parameters(params)
                    # 感情分析結果も送信
                    for conn in manager.active_connections:
                        await conn.send_json({
                            "type": "emotion",
                            "expression": expression.value,
                            "text": text,
                        })

            elif action == "speak":
                # テキスト+音声から感情付きリップシンク
                text = data.get("text", "")
                audio_path_str = data.get("audio_path", "")

                if text and audio_path_str:
                    audio_path = Path(audio_path_str)
                    if audio_path.exists():
                        # 感情分析結果を送信
                        expression, _ = emotion_driven.analyze_text(text)
                        for conn in manager.active_connections:
                            await conn.send_json({
                                "type": "emotion",
                                "expression": expression.value,
                                "text": text,
                            })

                        # 感情付きフレームを生成してストリーム
                        frames = emotion_driven.generate_speaking_frames(text, audio_path)
                        asyncio.create_task(manager.stream_frames(frames))

                        await websocket.send_json({
                            "type": "speaking",
                            "status": "started",
                            "frame_count": len(frames),
                            "expression": expression.value,
                        })
                    else:
                        await websocket.send_json({
                            "type": "error",
                            "message": f"Audio file not found: {audio_path_str}",
                        })

    except WebSocketDisconnect:
        manager.disconnect(websocket)


@router.get("/api/live2d/models")
async def list_models(models_dir: str = "models"):
    """利用可能なLive2Dモデル一覧"""
    models_path = Path(models_dir)
    if not models_path.exists():
        return {"models": []}

    models = []
    for model_json in models_path.glob("**/*.model3.json"):
        try:
            model = Live2DModel.from_model_json(model_json)
            models.append({
                "name": model.name,
                "path": str(model.model_path),
                "motions": model.motions,
                "expressions": model.expressions,
            })
        except Exception as e:
            logger.warning(f"Failed to load model {model_json}: {e}")

    return {"models": models}


@router.post("/api/live2d/analyze")
async def analyze_audio(audio_path: str, expression: str = "neutral"):
    """音声ファイルからLive2Dフレームを生成

    フレームデータはWebSocket経由でストリーム配信される
    """
    try:
        expr = Live2DExpression(expression)
    except ValueError:
        expr = Live2DExpression.NEUTRAL

    analyzer = Live2DLipsyncAnalyzer()
    frames = analyzer.analyze_audio(Path(audio_path), expr)

    # 非同期でストリーミング開始
    asyncio.create_task(manager.stream_frames(frames))

    return {
        "status": "streaming",
        "frame_count": len(frames),
        "duration_ms": frames[-1].timestamp_ms if frames else 0,
    }


@router.post("/api/live2d/stop")
async def stop_streaming():
    """ストリーミング停止"""
    manager.stop_streaming()
    return {"status": "stopped"}


@router.post("/api/live2d/emotion")
async def analyze_emotion(text: str):
    """テキストから感情を分析

    Args:
        text: 分析するテキスト

    Returns:
        expression: 検出された表情
        intensity: 感情の強度 (0.0-1.0)
        parameters: 対応するLive2Dパラメータ
    """
    expression, params = emotion_driven.get_expression_params(text)

    # 強度も取得
    result = emotion_driven.emotion_analyzer.analyze(text)

    return {
        "expression": expression.value,
        "intensity": result.intensity,
        "primary_emotion": result.primary.value,
        "secondary_emotion": result.secondary.value if result.secondary else None,
        "parameters": params.to_dict(),
        "raw_text": result.raw_text,
    }


@router.post("/api/live2d/speak")
async def speak_with_emotion(text: str, audio_path: str):
    """感情付き発話ストリーミング

    テキストから感情を分析し、音声ファイルと組み合わせて
    Live2Dフレームを生成してWebSocket経由でストリーム

    Args:
        text: 台詞テキスト
        audio_path: 音声ファイルパス

    Returns:
        status: ストリーミング状態
        expression: 検出された表情
        frame_count: 生成されたフレーム数
    """
    path = Path(audio_path)
    if not path.exists():
        return {"error": f"Audio file not found: {audio_path}"}

    expression, intensity = emotion_driven.analyze_text(text)
    frames = emotion_driven.generate_speaking_frames(text, path)

    # 非同期でストリーミング開始
    asyncio.create_task(manager.stream_frames(frames))

    return {
        "status": "streaming",
        "expression": expression.value,
        "intensity": intensity,
        "frame_count": len(frames),
        "duration_ms": frames[-1].timestamp_ms if frames else 0,
    }

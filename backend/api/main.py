"""Lobby Backend API - FastAPI Application"""

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .audio import router as audio_router
from .chat import router as chat_router
from .clip import router as clip_router
from .highlight import router as highlight_router
from .live import router as live_router
from .models import router as models_router
from .obs import router as obs_router
from .recording import router as recording_router
from .scene import router as scene_router
from .subtitle import router as subtitle_router
from .thumbnail import router as thumbnail_router
from .vrm import router as vrm_router
from .websocket import router as ws_router

# アプリケーション作成
app = FastAPI(
    title="Lobby",
    description="AI VTuber配信・収録ソフト API",
    version="0.8.0",
)

# CORS設定（開発用）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# WebSocket ルーター登録
app.include_router(ws_router)

# Live Mode ルーター登録
app.include_router(live_router)

# OBS ルーター登録
app.include_router(obs_router)

# Audio ルーター登録
app.include_router(audio_router)

# Scene ルーター登録
app.include_router(scene_router)

# VRM (3D) ルーター登録
app.include_router(vrm_router)

# Subtitle ルーター登録
app.include_router(subtitle_router)

# Highlight ルーター登録
app.include_router(highlight_router)

# Clip ルーター登録
app.include_router(clip_router)

# Models (local file serving) ルーター登録
app.include_router(models_router)

# Thumbnail ルーター登録
app.include_router(thumbnail_router)

# Chat proxy ルーター登録
app.include_router(chat_router)

# Recording Pipeline ルーター登録
app.include_router(recording_router)


@app.get("/")
async def root():
    return {
        "name": "Lobby",
        "version": "0.2.0",
        "status": "running",
    }


@app.get("/health")
async def health():
    return {"status": "healthy"}


# 静的ファイル（モデル等）のサーブ
models_dir = Path("models")
if models_dir.exists():
    app.mount("/models", StaticFiles(directory=str(models_dir)), name="models")


def run_server(host: str = "0.0.0.0", port: int = 8000):
    """開発サーバー起動"""
    import uvicorn
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    run_server()

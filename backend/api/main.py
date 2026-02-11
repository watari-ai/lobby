"""Lobby Backend API - FastAPI Application"""

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from loguru import logger

from .websocket import router as ws_router
from .live import router as live_router
from .obs import router as obs_router

# アプリケーション作成
app = FastAPI(
    title="Lobby",
    description="AI VTuber配信・収録ソフト API",
    version="0.4.0",
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

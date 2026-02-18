"""
OBS WebSocket API エンドポイント

OBS Studioとの連携機能をREST APIとして公開。
"""

from typing import Optional

from fastapi import APIRouter, HTTPException
from loguru import logger
from pydantic import BaseModel, Field

from ..integrations.obs import (
    LobbyOBSIntegration,
    OBSConfig,
    OBSRequestError,
    OBSWebSocketClient,
)

router = APIRouter(prefix="/api/obs", tags=["OBS"])

# グローバルOBSクライアントインスタンス
_obs_client: Optional[OBSWebSocketClient] = None
_lobby_obs: Optional[LobbyOBSIntegration] = None


# ========== リクエスト/レスポンスモデル ==========

class OBSConnectRequest(BaseModel):
    """OBS接続リクエスト"""
    host: str = Field(default="localhost", description="OBS WebSocketホスト")
    port: int = Field(default=4455, description="OBS WebSocketポート")
    password: Optional[str] = Field(default=None, description="認証パスワード")


class OBSStatusResponse(BaseModel):
    """OBS接続ステータス"""
    connected: bool
    host: Optional[str] = None
    port: Optional[int] = None


class SceneResponse(BaseModel):
    """シーン情報"""
    scene_name: str
    scene_index: int


class SceneItemResponse(BaseModel):
    """シーンアイテム情報"""
    scene_item_id: int
    source_name: str
    source_type: str
    scene_item_index: int
    scene_item_enabled: bool
    scene_item_locked: bool


class SetSceneRequest(BaseModel):
    """シーン切り替えリクエスト"""
    scene_name: str


class SetSceneItemEnabledRequest(BaseModel):
    """シーンアイテム表示/非表示リクエスト"""
    scene_name: str
    item_id: int
    enabled: bool


class AvatarSetupRequest(BaseModel):
    """アバターソース設定リクエスト"""
    source_name: str
    scene_name: str


class AvatarImageRequest(BaseModel):
    """アバター画像更新リクエスト"""
    image_path: str


class AvatarPositionRequest(BaseModel):
    """アバター位置設定リクエスト"""
    x: float
    y: float


class AvatarScaleRequest(BaseModel):
    """アバタースケール設定リクエスト"""
    scale_x: float
    scale_y: Optional[float] = None


class VirtualCamStatusResponse(BaseModel):
    """仮想カメラステータス"""
    active: bool


class RecordStatusResponse(BaseModel):
    """録画ステータス"""
    output_active: bool
    output_paused: bool
    output_timecode: str
    output_duration: int
    output_bytes: int


class StreamStatusResponse(BaseModel):
    """配信ステータス"""
    output_active: bool
    output_reconnecting: bool
    output_timecode: str
    output_duration: int
    output_bytes: int


# ========== ヘルパー関数 ==========

def get_obs_client() -> OBSWebSocketClient:
    """OBSクライアントを取得（未接続時はエラー）"""
    if _obs_client is None or not _obs_client.is_connected:
        raise HTTPException(status_code=503, detail="Not connected to OBS")
    return _obs_client


def get_lobby_obs() -> LobbyOBSIntegration:
    """Lobby OBS統合を取得"""
    global _lobby_obs
    obs = get_obs_client()
    if _lobby_obs is None:
        _lobby_obs = LobbyOBSIntegration(obs)
    return _lobby_obs


# ========== 接続管理 ==========

@router.post("/connect", response_model=OBSStatusResponse)
async def connect_obs(request: OBSConnectRequest):
    """OBS WebSocketに接続"""
    global _obs_client, _lobby_obs

    if _obs_client and _obs_client.is_connected:
        await _obs_client.disconnect()

    config = OBSConfig(
        host=request.host,
        port=request.port,
        password=request.password
    )
    _obs_client = OBSWebSocketClient(config)
    _lobby_obs = None

    success = await _obs_client.connect()
    if not success:
        raise HTTPException(status_code=503, detail="Failed to connect to OBS")

    logger.info(f"Connected to OBS at {request.host}:{request.port}")
    return OBSStatusResponse(
        connected=True,
        host=request.host,
        port=request.port
    )


@router.post("/disconnect")
async def disconnect_obs():
    """OBS WebSocketから切断"""
    global _obs_client, _lobby_obs

    if _obs_client:
        await _obs_client.disconnect()
        _obs_client = None
        _lobby_obs = None

    return {"status": "disconnected"}


@router.get("/status", response_model=OBSStatusResponse)
async def get_obs_status():
    """OBS接続ステータスを取得"""
    if _obs_client and _obs_client.is_connected:
        return OBSStatusResponse(
            connected=True,
            host=_obs_client.config.host,
            port=_obs_client.config.port
        )
    return OBSStatusResponse(connected=False)


# ========== シーン操作 ==========

@router.get("/scenes", response_model=list[SceneResponse])
async def get_scenes():
    """シーン一覧を取得"""
    obs = get_obs_client()
    try:
        scenes = await obs.get_scene_list()
        return [
            SceneResponse(scene_name=s.scene_name, scene_index=s.scene_index)
            for s in scenes
        ]
    except OBSRequestError as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/scenes/current")
async def get_current_scene():
    """現在のシーンを取得"""
    obs = get_obs_client()
    try:
        scene_name = await obs.get_current_scene()
        return {"scene_name": scene_name}
    except OBSRequestError as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/scenes/current")
async def set_current_scene(request: SetSceneRequest):
    """シーンを切り替え"""
    obs = get_obs_client()
    try:
        await obs.set_current_scene(request.scene_name)
        return {"status": "ok", "scene_name": request.scene_name}
    except OBSRequestError as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/scenes/{scene_name}/items", response_model=list[SceneItemResponse])
async def get_scene_items(scene_name: str):
    """シーン内のアイテム一覧を取得"""
    obs = get_obs_client()
    try:
        items = await obs.get_scene_items(scene_name)
        return [
            SceneItemResponse(
                scene_item_id=i.scene_item_id,
                source_name=i.source_name,
                source_type=i.source_type,
                scene_item_index=i.scene_item_index,
                scene_item_enabled=i.scene_item_enabled,
                scene_item_locked=i.scene_item_locked
            )
            for i in items
        ]
    except OBSRequestError as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/scenes/items/enabled")
async def set_scene_item_enabled(request: SetSceneItemEnabledRequest):
    """シーンアイテムの表示/非表示を切り替え"""
    obs = get_obs_client()
    try:
        await obs.set_scene_item_enabled(
            request.scene_name, request.item_id, request.enabled
        )
        return {"status": "ok"}
    except OBSRequestError as e:
        raise HTTPException(status_code=500, detail=str(e))


# ========== アバター操作（Lobby統合）==========

@router.post("/avatar/setup")
async def setup_avatar(request: AvatarSetupRequest):
    """アバターソースを設定"""
    lobby_obs = get_lobby_obs()
    await lobby_obs.setup_avatar_source(request.source_name, request.scene_name)
    return {"status": "ok"}


@router.post("/avatar/image")
async def update_avatar_image(request: AvatarImageRequest):
    """アバター画像を更新"""
    lobby_obs = get_lobby_obs()
    await lobby_obs.update_avatar_image(request.image_path)
    return {"status": "ok"}


@router.post("/avatar/show")
async def show_avatar():
    """アバターを表示"""
    lobby_obs = get_lobby_obs()
    await lobby_obs.show_avatar()
    return {"status": "ok"}


@router.post("/avatar/hide")
async def hide_avatar():
    """アバターを非表示"""
    lobby_obs = get_lobby_obs()
    await lobby_obs.hide_avatar()
    return {"status": "ok"}


@router.post("/avatar/position")
async def set_avatar_position(request: AvatarPositionRequest):
    """アバターの位置を設定"""
    lobby_obs = get_lobby_obs()
    await lobby_obs.set_avatar_position(request.x, request.y)
    return {"status": "ok"}


@router.post("/avatar/scale")
async def set_avatar_scale(request: AvatarScaleRequest):
    """アバターのスケールを設定"""
    lobby_obs = get_lobby_obs()
    await lobby_obs.set_avatar_scale(request.scale_x, request.scale_y)
    return {"status": "ok"}


# ========== 仮想カメラ ==========

@router.get("/virtualcam/status", response_model=VirtualCamStatusResponse)
async def get_virtual_cam_status():
    """仮想カメラの状態を取得"""
    obs = get_obs_client()
    try:
        active = await obs.get_virtual_cam_status()
        return VirtualCamStatusResponse(active=active)
    except OBSRequestError as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/virtualcam/start")
async def start_virtual_cam():
    """仮想カメラを開始"""
    obs = get_obs_client()
    try:
        await obs.start_virtual_cam()
        return {"status": "started"}
    except OBSRequestError as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/virtualcam/stop")
async def stop_virtual_cam():
    """仮想カメラを停止"""
    obs = get_obs_client()
    try:
        await obs.stop_virtual_cam()
        return {"status": "stopped"}
    except OBSRequestError as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/virtualcam/toggle")
async def toggle_virtual_cam():
    """仮想カメラをトグル"""
    obs = get_obs_client()
    try:
        active = await obs.toggle_virtual_cam()
        return {"active": active}
    except OBSRequestError as e:
        raise HTTPException(status_code=500, detail=str(e))


# ========== 録画 ==========

@router.get("/record/status", response_model=RecordStatusResponse)
async def get_record_status():
    """録画状態を取得"""
    obs = get_obs_client()
    try:
        status = await obs.get_record_status()
        return RecordStatusResponse(
            output_active=status.get("outputActive", False),
            output_paused=status.get("outputPaused", False),
            output_timecode=status.get("outputTimecode", "00:00:00"),
            output_duration=status.get("outputDuration", 0),
            output_bytes=status.get("outputBytes", 0)
        )
    except OBSRequestError as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/record/start")
async def start_record():
    """録画を開始"""
    obs = get_obs_client()
    try:
        await obs.start_record()
        return {"status": "started"}
    except OBSRequestError as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/record/stop")
async def stop_record():
    """録画を停止"""
    obs = get_obs_client()
    try:
        output_path = await obs.stop_record()
        return {"status": "stopped", "output_path": output_path}
    except OBSRequestError as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/record/pause")
async def pause_record():
    """録画を一時停止"""
    obs = get_obs_client()
    try:
        await obs.pause_record()
        return {"status": "paused"}
    except OBSRequestError as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/record/resume")
async def resume_record():
    """録画を再開"""
    obs = get_obs_client()
    try:
        await obs.resume_record()
        return {"status": "resumed"}
    except OBSRequestError as e:
        raise HTTPException(status_code=500, detail=str(e))


# ========== ストリーミング ==========

@router.get("/stream/status", response_model=StreamStatusResponse)
async def get_stream_status():
    """配信状態を取得"""
    obs = get_obs_client()
    try:
        status = await obs.get_stream_status()
        return StreamStatusResponse(
            output_active=status.get("outputActive", False),
            output_reconnecting=status.get("outputReconnecting", False),
            output_timecode=status.get("outputTimecode", "00:00:00"),
            output_duration=status.get("outputDuration", 0),
            output_bytes=status.get("outputBytes", 0)
        )
    except OBSRequestError as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/stream/start")
async def start_stream():
    """配信を開始"""
    obs = get_obs_client()
    try:
        await obs.start_stream()
        return {"status": "started"}
    except OBSRequestError as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/stream/stop")
async def stop_stream():
    """配信を停止"""
    obs = get_obs_client()
    try:
        await obs.stop_stream()
        return {"status": "stopped"}
    except OBSRequestError as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/stream/toggle")
async def toggle_stream():
    """配信をトグル"""
    obs = get_obs_client()
    try:
        active = await obs.toggle_stream()
        return {"active": active}
    except OBSRequestError as e:
        raise HTTPException(status_code=500, detail=str(e))


# ========== 録画セッション（Lobby統合）==========

@router.post("/session/start")
async def start_recording_session():
    """録画セッションを開始（仮想カメラ + 録画）"""
    lobby_obs = get_lobby_obs()
    try:
        await lobby_obs.start_recording_session()
        return {"status": "started"}
    except OBSRequestError as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/session/stop")
async def stop_recording_session():
    """録画セッションを停止"""
    lobby_obs = get_lobby_obs()
    try:
        output_path = await lobby_obs.stop_recording_session()
        return {"status": "stopped", "output_path": output_path}
    except OBSRequestError as e:
        raise HTTPException(status_code=500, detail=str(e))

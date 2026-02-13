"""
Scene Management API for Lobby

REST API endpoints for scene control:
- GET /api/scene/list - シーン一覧
- GET /api/scene/current - 現在のシーン
- POST /api/scene/switch - シーン切り替え
- POST /api/scene/camera - カメラ設定変更
- POST /api/scene/overlay - オーバーレイ追加
- DELETE /api/scene/overlay/{id} - オーバーレイ削除
- POST /api/scene/caption - テロップ表示
"""

from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..core.scene import (
    Background,
    CameraAngle,
    CameraSettings,
    Overlay,
    OverlayType,
    Scene,
    get_scene_manager,
)

router = APIRouter(prefix="/api/scene", tags=["scene"])


# === Request/Response Models ===

class SwitchSceneRequest(BaseModel):
    """シーン切り替えリクエスト"""
    name: str
    transition: str = "fade"  # fade, cut, slide


class CameraRequest(BaseModel):
    """カメラ設定リクエスト"""
    angle: Optional[str] = None  # close_up, medium, full, custom
    zoom: Optional[float] = Field(None, ge=0.1, le=3.0)
    offset_x: Optional[float] = Field(None, ge=-1.0, le=1.0)
    offset_y: Optional[float] = Field(None, ge=-1.0, le=1.0)


class OverlayRequest(BaseModel):
    """オーバーレイ追加リクエスト"""
    id: str
    type: str = "text"  # text, image, effect, frame
    content: str
    position: list[float] = [0.5, 0.5]
    size: list[float] = [0.8, 0.1]
    visible: bool = True
    style: dict = {}
    z_index: int = 10
    animation: Optional[str] = None


class CaptionRequest(BaseModel):
    """テロップ表示リクエスト"""
    text: str
    duration_ms: int = Field(3000, ge=500, le=30000)


class CreateSceneRequest(BaseModel):
    """シーン作成リクエスト"""
    name: str
    background: dict = {}
    camera: dict = {}
    overlays: list[dict] = []
    avatar_visible: bool = True
    avatar_position: list[float] = [0.5, 0.5]
    avatar_scale: float = 1.0


class UpdateSceneRequest(BaseModel):
    """シーン更新リクエスト"""
    background: Optional[dict] = None
    camera: Optional[dict] = None
    overlays: Optional[list[dict]] = None
    avatar_visible: Optional[bool] = None
    avatar_position: Optional[list[float]] = None
    avatar_scale: Optional[float] = None


class SceneResponse(BaseModel):
    """シーンレスポンス"""
    name: str
    background: dict
    camera: dict
    overlays: list[dict]
    avatar_visible: bool
    avatar_position: list[float]
    avatar_scale: float


# === Endpoints ===

@router.get("/list")
async def list_scenes():
    """シーン一覧を取得"""
    manager = get_scene_manager()
    scenes = []
    for name in manager.list_scenes():
        scene = manager.get_scene(name)
        if scene:
            scenes.append({
                "name": name,
                "is_current": manager.current_scene and manager.current_scene.name == name
            })
    return {"scenes": scenes}


@router.get("/current")
async def get_current_scene():
    """現在のシーンを取得"""
    manager = get_scene_manager()
    scene = manager.get_current_scene()
    if not scene:
        raise HTTPException(status_code=404, detail="No current scene")
    return scene.to_dict()


@router.get("/{name}")
async def get_scene(name: str):
    """指定シーンを取得"""
    manager = get_scene_manager()
    scene = manager.get_scene(name)
    if not scene:
        raise HTTPException(status_code=404, detail=f"Scene '{name}' not found")
    return scene.to_dict()


@router.post("/switch")
async def switch_scene(request: SwitchSceneRequest):
    """シーンを切り替え"""
    manager = get_scene_manager()
    success = await manager.switch_scene(request.name, request.transition)
    if not success:
        raise HTTPException(status_code=404, detail=f"Scene '{request.name}' not found")
    return {
        "success": True,
        "scene": request.name,
        "transition": request.transition
    }


@router.post("/create")
async def create_scene(request: CreateSceneRequest):
    """新しいシーンを作成"""
    manager = get_scene_manager()

    # 既存チェック
    if manager.get_scene(request.name):
        raise HTTPException(status_code=409, detail=f"Scene '{request.name}' already exists")

    # シーン作成
    scene = Scene(
        name=request.name,
        background=Background.from_dict(request.background) if request.background else Background(name="default", type="color", source="#1a1a2e"),
        camera=CameraSettings.from_dict(request.camera) if request.camera else CameraSettings.preset(CameraAngle.MEDIUM),
        overlays=[Overlay.from_dict(o) for o in request.overlays],
        avatar_visible=request.avatar_visible,
        avatar_position=tuple(request.avatar_position),
        avatar_scale=request.avatar_scale
    )

    if not manager.add_scene(scene):
        raise HTTPException(status_code=500, detail="Failed to create scene")

    return {"success": True, "scene": scene.to_dict()}


@router.put("/{name}")
async def update_scene(name: str, request: UpdateSceneRequest):
    """シーンを更新"""
    manager = get_scene_manager()

    updates = {}
    if request.background is not None:
        updates["background"] = request.background
    if request.camera is not None:
        updates["camera"] = request.camera
    if request.overlays is not None:
        updates["overlays"] = request.overlays
    if request.avatar_visible is not None:
        updates["avatar_visible"] = request.avatar_visible
    if request.avatar_position is not None:
        updates["avatar_position"] = request.avatar_position
    if request.avatar_scale is not None:
        updates["avatar_scale"] = request.avatar_scale

    success = manager.update_scene(name, updates)
    if not success:
        raise HTTPException(status_code=404, detail=f"Scene '{name}' not found")

    return {"success": True, "scene": manager.get_scene(name).to_dict()}


@router.delete("/{name}")
async def delete_scene(name: str):
    """シーンを削除"""
    manager = get_scene_manager()
    success = manager.delete_scene(name)
    if not success:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot delete scene '{name}' (default scenes cannot be deleted)"
        )
    return {"success": True, "deleted": name}


@router.post("/camera")
async def set_camera(request: CameraRequest):
    """カメラ設定を変更"""
    manager = get_scene_manager()

    angle = None
    if request.angle:
        try:
            angle = CameraAngle(request.angle)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid angle: {request.angle}")

    success = await manager.set_camera(
        angle=angle,
        zoom=request.zoom,
        offset_x=request.offset_x,
        offset_y=request.offset_y
    )

    if not success:
        raise HTTPException(status_code=400, detail="No current scene")

    scene = manager.get_current_scene()
    return {
        "success": True,
        "camera": scene.camera.to_dict() if scene else None
    }


@router.post("/overlay")
async def add_overlay(request: OverlayRequest):
    """オーバーレイを追加"""
    manager = get_scene_manager()

    try:
        overlay_type = OverlayType(request.type)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid overlay type: {request.type}")

    overlay = Overlay(
        id=request.id,
        type=overlay_type,
        content=request.content,
        position=tuple(request.position),
        size=tuple(request.size),
        visible=request.visible,
        style=request.style,
        z_index=request.z_index,
        animation=request.animation
    )

    success = manager.add_overlay(overlay)
    if not success:
        raise HTTPException(status_code=400, detail="No current scene")

    return {"success": True, "overlay": overlay.to_dict()}


@router.put("/overlay/{overlay_id}")
async def update_overlay(overlay_id: str, updates: dict):
    """オーバーレイを更新"""
    manager = get_scene_manager()
    success = manager.update_overlay(overlay_id, updates)
    if not success:
        raise HTTPException(status_code=404, detail=f"Overlay '{overlay_id}' not found")
    return {"success": True, "overlay_id": overlay_id}


@router.delete("/overlay/{overlay_id}")
async def remove_overlay(overlay_id: str):
    """オーバーレイを削除"""
    manager = get_scene_manager()
    success = manager.remove_overlay(overlay_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"Overlay '{overlay_id}' not found")
    return {"success": True, "deleted": overlay_id}


@router.post("/caption")
async def show_caption(request: CaptionRequest):
    """テロップを表示"""
    manager = get_scene_manager()
    caption_id = manager.show_caption(request.text, request.duration_ms)
    return {
        "success": True,
        "caption_id": caption_id,
        "text": request.text,
        "duration_ms": request.duration_ms
    }


@router.post("/save")
async def save_scenes():
    """シーン設定を保存"""
    manager = get_scene_manager()
    success = manager.save_scenes()
    return {"success": success}


@router.post("/load")
async def load_scenes():
    """シーン設定を読み込み"""
    manager = get_scene_manager()
    success = manager.load_scenes()
    return {"success": success}

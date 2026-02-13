"""
Scene Manager for Lobby - AI VTuber配信ソフト

シーン管理機能:
- 背景切り替え
- カメラアングル（アップ/引き/カスタム）
- オーバーレイ（テロップ、エフェクト）
- シーンプリセット
"""

import inspect
import json
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional


class CameraAngle(Enum):
    """カメラアングルプリセット"""
    CLOSE_UP = "close_up"       # アップ（顔中心）
    MEDIUM = "medium"           # ミディアム（上半身）
    FULL = "full"               # 全身
    CUSTOM = "custom"           # カスタム


class OverlayType(Enum):
    """オーバーレイの種類"""
    TEXT = "text"               # テロップ
    IMAGE = "image"             # 画像オーバーレイ
    EFFECT = "effect"           # エフェクト（パーティクル等）
    FRAME = "frame"             # フレーム/ボーダー


@dataclass
class CameraSettings:
    """カメラ設定"""
    angle: CameraAngle = CameraAngle.MEDIUM
    zoom: float = 1.0           # 1.0 = 標準
    offset_x: float = 0.0       # X方向オフセット（-1.0 〜 1.0）
    offset_y: float = 0.0       # Y方向オフセット（-1.0 〜 1.0）
    transition_ms: int = 500    # トランジション時間（ミリ秒）

    def to_dict(self) -> dict:
        return {
            "angle": self.angle.value,
            "zoom": self.zoom,
            "offset_x": self.offset_x,
            "offset_y": self.offset_y,
            "transition_ms": self.transition_ms
        }

    @classmethod
    def from_dict(cls, data: dict) -> "CameraSettings":
        return cls(
            angle=CameraAngle(data.get("angle", "medium")),
            zoom=data.get("zoom", 1.0),
            offset_x=data.get("offset_x", 0.0),
            offset_y=data.get("offset_y", 0.0),
            transition_ms=data.get("transition_ms", 500)
        )

    @classmethod
    def preset(cls, angle: CameraAngle) -> "CameraSettings":
        """プリセットカメラ設定を返す"""
        presets = {
            CameraAngle.CLOSE_UP: cls(angle=CameraAngle.CLOSE_UP, zoom=1.5, offset_y=0.2),
            CameraAngle.MEDIUM: cls(angle=CameraAngle.MEDIUM, zoom=1.0),
            CameraAngle.FULL: cls(angle=CameraAngle.FULL, zoom=0.7, offset_y=-0.1),
            CameraAngle.CUSTOM: cls(angle=CameraAngle.CUSTOM)
        }
        return presets.get(angle, presets[CameraAngle.MEDIUM])


@dataclass
class Background:
    """背景設定"""
    name: str
    type: str = "image"          # image, video, color, transparent
    source: str = ""             # ファイルパス or カラーコード
    loop: bool = True            # 動画の場合ループするか
    opacity: float = 1.0

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "type": self.type,
            "source": self.source,
            "loop": self.loop,
            "opacity": self.opacity
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Background":
        return cls(
            name=data.get("name", "default"),
            type=data.get("type", "image"),
            source=data.get("source", ""),
            loop=data.get("loop", True),
            opacity=data.get("opacity", 1.0)
        )


@dataclass
class Overlay:
    """オーバーレイ設定"""
    id: str
    type: OverlayType
    content: str                 # テキスト or ファイルパス
    position: tuple[float, float] = (0.5, 0.9)  # (x, y) 0.0-1.0
    size: tuple[float, float] = (0.8, 0.1)      # (width, height) 0.0-1.0
    visible: bool = True
    style: dict = field(default_factory=dict)   # フォント、色など
    z_index: int = 10
    animation: Optional[str] = None  # fade_in, slide_in, bounce, etc.

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "type": self.type.value,
            "content": self.content,
            "position": list(self.position),
            "size": list(self.size),
            "visible": self.visible,
            "style": self.style,
            "z_index": self.z_index,
            "animation": self.animation
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Overlay":
        return cls(
            id=data.get("id", "overlay"),
            type=OverlayType(data.get("type", "text")),
            content=data.get("content", ""),
            position=tuple(data.get("position", [0.5, 0.9])),
            size=tuple(data.get("size", [0.8, 0.1])),
            visible=data.get("visible", True),
            style=data.get("style", {}),
            z_index=data.get("z_index", 10),
            animation=data.get("animation")
        )


@dataclass
class Scene:
    """シーン設定"""
    name: str
    background: Background
    camera: CameraSettings
    overlays: list[Overlay] = field(default_factory=list)
    avatar_visible: bool = True
    avatar_position: tuple[float, float] = (0.5, 0.5)  # アバター位置
    avatar_scale: float = 1.0
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "background": self.background.to_dict(),
            "camera": self.camera.to_dict(),
            "overlays": [o.to_dict() for o in self.overlays],
            "avatar_visible": self.avatar_visible,
            "avatar_position": list(self.avatar_position),
            "avatar_scale": self.avatar_scale,
            "metadata": self.metadata
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Scene":
        return cls(
            name=data.get("name", "default"),
            background=Background.from_dict(data.get("background", {})),
            camera=CameraSettings.from_dict(data.get("camera", {})),
            overlays=[Overlay.from_dict(o) for o in data.get("overlays", [])],
            avatar_visible=data.get("avatar_visible", True),
            avatar_position=tuple(data.get("avatar_position", [0.5, 0.5])),
            avatar_scale=data.get("avatar_scale", 1.0),
            metadata=data.get("metadata", {})
        )


class SceneManager:
    """シーンマネージャー"""

    def __init__(self, config_dir: Optional[Path] = None):
        self.config_dir = config_dir or Path("config/scenes")
        self.scenes: dict[str, Scene] = {}
        self.current_scene: Optional[Scene] = None
        self._callbacks: list[callable] = []
        self._init_default_scenes()

    def _init_default_scenes(self):
        """デフォルトシーンを初期化"""
        # トーク用シーン（デフォルト）
        self.scenes["talk"] = Scene(
            name="talk",
            background=Background(name="default", type="color", source="#1a1a2e"),
            camera=CameraSettings.preset(CameraAngle.MEDIUM),
            overlays=[
                Overlay(
                    id="name_plate",
                    type=OverlayType.TEXT,
                    content="倉土ロビィ",
                    position=(0.5, 0.95),
                    size=(0.3, 0.05),
                    style={"font_size": 24, "color": "#ffffff", "bg_color": "#ff6b6b80"}
                )
            ]
        )

        # リアクション用シーン（アップ）
        self.scenes["reaction"] = Scene(
            name="reaction",
            background=Background(name="default", type="color", source="#1a1a2e"),
            camera=CameraSettings.preset(CameraAngle.CLOSE_UP),
            overlays=[]
        )

        # ゲーム配信シーン
        self.scenes["gaming"] = Scene(
            name="gaming",
            background=Background(name="transparent", type="transparent", source=""),
            camera=CameraSettings(
                angle=CameraAngle.CUSTOM,
                zoom=0.5,
                offset_x=0.7,
                offset_y=0.3
            ),
            avatar_position=(0.85, 0.75),
            avatar_scale=0.4,
            overlays=[]
        )

        # オープニング/エンディング
        self.scenes["opening"] = Scene(
            name="opening",
            background=Background(name="opening_bg", type="color", source="#ff6b6b"),
            camera=CameraSettings.preset(CameraAngle.FULL),
            overlays=[
                Overlay(
                    id="title",
                    type=OverlayType.TEXT,
                    content="ロビィの配信っす！",
                    position=(0.5, 0.2),
                    size=(0.8, 0.15),
                    style={"font_size": 48, "color": "#ffffff", "font_weight": "bold"},
                    animation="bounce"
                )
            ]
        )

        self.current_scene = self.scenes["talk"]

    def on_scene_change(self, callback: callable):
        """シーン変更時のコールバックを登録"""
        self._callbacks.append(callback)

    async def _notify_callbacks(self, scene: Scene, transition: str = "fade"):
        """コールバックを通知"""
        for callback in self._callbacks:
            if inspect.iscoroutinefunction(callback):
                await callback(scene, transition)
            else:
                callback(scene, transition)

    def get_scene(self, name: str) -> Optional[Scene]:
        """シーンを取得"""
        return self.scenes.get(name)

    def list_scenes(self) -> list[str]:
        """シーン一覧を取得"""
        return list(self.scenes.keys())

    def get_current_scene(self) -> Optional[Scene]:
        """現在のシーンを取得"""
        return self.current_scene

    async def switch_scene(self, name: str, transition: str = "fade") -> bool:
        """シーンを切り替え"""
        if name not in self.scenes:
            return False

        self.current_scene = self.scenes[name]
        await self._notify_callbacks(self.current_scene, transition)
        return True

    def add_scene(self, scene: Scene) -> bool:
        """シーンを追加"""
        if scene.name in self.scenes:
            return False
        self.scenes[scene.name] = scene
        return True

    def update_scene(self, name: str, updates: dict) -> bool:
        """シーンを更新"""
        if name not in self.scenes:
            return False

        scene = self.scenes[name]

        if "background" in updates:
            scene.background = Background.from_dict(updates["background"])
        if "camera" in updates:
            scene.camera = CameraSettings.from_dict(updates["camera"])
        if "overlays" in updates:
            scene.overlays = [Overlay.from_dict(o) for o in updates["overlays"]]
        if "avatar_visible" in updates:
            scene.avatar_visible = updates["avatar_visible"]
        if "avatar_position" in updates:
            scene.avatar_position = tuple(updates["avatar_position"])
        if "avatar_scale" in updates:
            scene.avatar_scale = updates["avatar_scale"]

        return True

    def delete_scene(self, name: str) -> bool:
        """シーンを削除（デフォルトシーンは削除不可）"""
        if name in ["talk", "reaction", "gaming", "opening"]:
            return False
        if name not in self.scenes:
            return False

        del self.scenes[name]
        if self.current_scene and self.current_scene.name == name:
            self.current_scene = self.scenes["talk"]
        return True

    # カメラ操作
    async def set_camera(self, angle: Optional[CameraAngle] = None,
                         zoom: Optional[float] = None,
                         offset_x: Optional[float] = None,
                         offset_y: Optional[float] = None) -> bool:
        """カメラ設定を変更"""
        if not self.current_scene:
            return False

        camera = self.current_scene.camera
        if angle:
            camera.angle = angle
        if zoom is not None:
            camera.zoom = max(0.1, min(3.0, zoom))
        if offset_x is not None:
            camera.offset_x = max(-1.0, min(1.0, offset_x))
        if offset_y is not None:
            camera.offset_y = max(-1.0, min(1.0, offset_y))

        await self._notify_callbacks(self.current_scene, "instant")
        return True

    # オーバーレイ操作
    def add_overlay(self, overlay: Overlay) -> bool:
        """オーバーレイを追加"""
        if not self.current_scene:
            return False

        # 同じIDがあれば削除
        self.current_scene.overlays = [
            o for o in self.current_scene.overlays if o.id != overlay.id
        ]
        self.current_scene.overlays.append(overlay)
        return True

    def remove_overlay(self, overlay_id: str) -> bool:
        """オーバーレイを削除"""
        if not self.current_scene:
            return False

        before = len(self.current_scene.overlays)
        self.current_scene.overlays = [
            o for o in self.current_scene.overlays if o.id != overlay_id
        ]
        return len(self.current_scene.overlays) < before

    def update_overlay(self, overlay_id: str, updates: dict) -> bool:
        """オーバーレイを更新"""
        if not self.current_scene:
            return False

        for overlay in self.current_scene.overlays:
            if overlay.id == overlay_id:
                if "content" in updates:
                    overlay.content = updates["content"]
                if "visible" in updates:
                    overlay.visible = updates["visible"]
                if "position" in updates:
                    overlay.position = tuple(updates["position"])
                if "style" in updates:
                    overlay.style.update(updates["style"])
                return True
        return False

    def show_caption(self, text: str, duration_ms: int = 3000) -> str:
        """字幕（テロップ）を表示"""
        caption_id = f"caption_{id(text)}"
        overlay = Overlay(
            id=caption_id,
            type=OverlayType.TEXT,
            content=text,
            position=(0.5, 0.85),
            size=(0.9, 0.08),
            style={
                "font_size": 32,
                "color": "#ffffff",
                "bg_color": "#00000080",
                "padding": 10
            },
            animation="fade_in"
        )
        self.add_overlay(overlay)
        return caption_id

    # 保存/読み込み
    def save_scenes(self, filepath: Optional[Path] = None) -> bool:
        """シーン設定を保存"""
        path = filepath or self.config_dir / "scenes.json"
        path.parent.mkdir(parents=True, exist_ok=True)

        data = {name: scene.to_dict() for name, scene in self.scenes.items()}
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        return True

    def load_scenes(self, filepath: Optional[Path] = None) -> bool:
        """シーン設定を読み込み"""
        path = filepath or self.config_dir / "scenes.json"
        if not path.exists():
            return False

        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        for name, scene_data in data.items():
            self.scenes[name] = Scene.from_dict(scene_data)

        return True


# シングルトンインスタンス
_scene_manager: Optional[SceneManager] = None


def get_scene_manager() -> SceneManager:
    """SceneManagerのシングルトンを取得"""
    global _scene_manager
    if _scene_manager is None:
        _scene_manager = SceneManager()
    return _scene_manager

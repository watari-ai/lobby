"""Tests for Scene Manager"""


import pytest

from backend.core.scene import (
    Background,
    CameraAngle,
    CameraSettings,
    Overlay,
    OverlayType,
    Scene,
    SceneManager,
    get_scene_manager,
)


class TestCameraSettings:
    """CameraSettings tests"""

    def test_preset_close_up(self):
        camera = CameraSettings.preset(CameraAngle.CLOSE_UP)
        assert camera.angle == CameraAngle.CLOSE_UP
        assert camera.zoom == 1.5
        assert camera.offset_y == 0.2

    def test_preset_medium(self):
        camera = CameraSettings.preset(CameraAngle.MEDIUM)
        assert camera.angle == CameraAngle.MEDIUM
        assert camera.zoom == 1.0

    def test_preset_full(self):
        camera = CameraSettings.preset(CameraAngle.FULL)
        assert camera.angle == CameraAngle.FULL
        assert camera.zoom == 0.7

    def test_to_dict_from_dict(self):
        camera = CameraSettings(
            angle=CameraAngle.CUSTOM,
            zoom=1.2,
            offset_x=0.5,
            offset_y=-0.3
        )
        data = camera.to_dict()
        restored = CameraSettings.from_dict(data)

        assert restored.angle == camera.angle
        assert restored.zoom == camera.zoom
        assert restored.offset_x == camera.offset_x
        assert restored.offset_y == camera.offset_y


class TestBackground:
    """Background tests"""

    def test_default(self):
        bg = Background(name="test")
        assert bg.type == "image"
        assert bg.opacity == 1.0

    def test_to_dict_from_dict(self):
        bg = Background(
            name="custom",
            type="video",
            source="/path/to/video.mp4",
            loop=False,
            opacity=0.8
        )
        data = bg.to_dict()
        restored = Background.from_dict(data)

        assert restored.name == bg.name
        assert restored.type == bg.type
        assert restored.source == bg.source
        assert restored.loop == bg.loop
        assert restored.opacity == bg.opacity


class TestOverlay:
    """Overlay tests"""

    def test_text_overlay(self):
        overlay = Overlay(
            id="caption",
            type=OverlayType.TEXT,
            content="Hello World",
            position=(0.5, 0.9)
        )
        assert overlay.type == OverlayType.TEXT
        assert overlay.visible

    def test_to_dict_from_dict(self):
        overlay = Overlay(
            id="test",
            type=OverlayType.IMAGE,
            content="/path/to/image.png",
            position=(0.2, 0.3),
            size=(0.5, 0.5),
            visible=False,
            style={"opacity": 0.7},
            animation="fade_in"
        )
        data = overlay.to_dict()
        restored = Overlay.from_dict(data)

        assert restored.id == overlay.id
        assert restored.type == overlay.type
        assert restored.content == overlay.content
        assert restored.animation == overlay.animation


class TestScene:
    """Scene tests"""

    def test_create_scene(self):
        scene = Scene(
            name="test",
            background=Background(name="bg", type="color", source="#000000"),
            camera=CameraSettings.preset(CameraAngle.MEDIUM)
        )
        assert scene.name == "test"
        assert scene.avatar_visible
        assert scene.avatar_scale == 1.0

    def test_to_dict_from_dict(self):
        scene = Scene(
            name="complex",
            background=Background(name="bg", type="color", source="#ffffff"),
            camera=CameraSettings.preset(CameraAngle.CLOSE_UP),
            overlays=[
                Overlay(id="text1", type=OverlayType.TEXT, content="Test")
            ],
            avatar_visible=False,
            avatar_position=(0.3, 0.7),
            avatar_scale=0.8
        )
        data = scene.to_dict()
        restored = Scene.from_dict(data)

        assert restored.name == scene.name
        assert restored.avatar_visible == scene.avatar_visible
        assert len(restored.overlays) == 1


class TestSceneManager:
    """SceneManager tests"""

    def test_default_scenes(self):
        manager = SceneManager()
        scenes = manager.list_scenes()

        assert "talk" in scenes
        assert "reaction" in scenes
        assert "gaming" in scenes
        assert "opening" in scenes

    def test_current_scene_default(self):
        manager = SceneManager()
        current = manager.get_current_scene()

        assert current is not None
        assert current.name == "talk"

    @pytest.mark.asyncio
    async def test_switch_scene(self):
        manager = SceneManager()

        success = await manager.switch_scene("reaction")
        assert success
        assert manager.get_current_scene().name == "reaction"

    @pytest.mark.asyncio
    async def test_switch_scene_invalid(self):
        manager = SceneManager()

        success = await manager.switch_scene("nonexistent")
        assert not success

    def test_add_scene(self):
        manager = SceneManager()

        new_scene = Scene(
            name="custom",
            background=Background(name="bg", type="color", source="#ff0000"),
            camera=CameraSettings.preset(CameraAngle.MEDIUM)
        )

        success = manager.add_scene(new_scene)
        assert success
        assert "custom" in manager.list_scenes()

    def test_add_scene_duplicate(self):
        manager = SceneManager()

        new_scene = Scene(
            name="talk",  # already exists
            background=Background(name="bg", type="color", source="#ff0000"),
            camera=CameraSettings.preset(CameraAngle.MEDIUM)
        )

        success = manager.add_scene(new_scene)
        assert not success

    def test_update_scene(self):
        manager = SceneManager()

        success = manager.update_scene("talk", {
            "avatar_scale": 1.5,
            "avatar_visible": False
        })

        assert success
        scene = manager.get_scene("talk")
        assert scene.avatar_scale == 1.5
        assert not scene.avatar_visible

    def test_delete_scene_default(self):
        manager = SceneManager()

        # Default scenes cannot be deleted
        success = manager.delete_scene("talk")
        assert not success

    def test_delete_scene_custom(self):
        manager = SceneManager()

        # Add and delete custom scene
        new_scene = Scene(
            name="deletable",
            background=Background(name="bg", type="color", source="#000"),
            camera=CameraSettings.preset(CameraAngle.MEDIUM)
        )
        manager.add_scene(new_scene)

        success = manager.delete_scene("deletable")
        assert success
        assert "deletable" not in manager.list_scenes()

    @pytest.mark.asyncio
    async def test_set_camera(self):
        manager = SceneManager()

        success = await manager.set_camera(zoom=2.0, offset_x=0.5)
        assert success

        camera = manager.get_current_scene().camera
        assert camera.zoom == 2.0
        assert camera.offset_x == 0.5

    @pytest.mark.asyncio
    async def test_set_camera_bounds(self):
        manager = SceneManager()

        # Test clamping
        await manager.set_camera(zoom=5.0)  # Max is 3.0
        assert manager.get_current_scene().camera.zoom == 3.0

        await manager.set_camera(zoom=0.05)  # Min is 0.1
        assert manager.get_current_scene().camera.zoom == 0.1

    def test_add_overlay(self):
        manager = SceneManager()

        overlay = Overlay(
            id="test_overlay",
            type=OverlayType.TEXT,
            content="Test"
        )

        success = manager.add_overlay(overlay)
        assert success

        overlays = manager.get_current_scene().overlays
        assert any(o.id == "test_overlay" for o in overlays)

    def test_remove_overlay(self):
        manager = SceneManager()

        # Default talk scene has name_plate overlay
        success = manager.remove_overlay("name_plate")
        assert success

        overlays = manager.get_current_scene().overlays
        assert not any(o.id == "name_plate" for o in overlays)

    def test_update_overlay(self):
        manager = SceneManager()

        success = manager.update_overlay("name_plate", {
            "content": "Updated Name",
            "visible": False
        })
        assert success

        overlays = manager.get_current_scene().overlays
        name_plate = next((o for o in overlays if o.id == "name_plate"), None)
        assert name_plate is not None
        assert name_plate.content == "Updated Name"
        assert not name_plate.visible

    def test_show_caption(self):
        manager = SceneManager()

        caption_id = manager.show_caption("Hello!", 5000)
        assert caption_id is not None

        overlays = manager.get_current_scene().overlays
        assert any(o.id == caption_id for o in overlays)

    @pytest.mark.asyncio
    async def test_scene_change_callback(self):
        manager = SceneManager()
        callback_called = False
        received_scene = None

        async def callback(scene, transition):
            nonlocal callback_called, received_scene
            callback_called = True
            received_scene = scene

        manager.on_scene_change(callback)
        await manager.switch_scene("reaction")

        assert callback_called
        assert received_scene.name == "reaction"


class TestGetSceneManager:
    """get_scene_manager singleton tests"""

    def test_singleton(self):
        manager1 = get_scene_manager()
        manager2 = get_scene_manager()

        # 同一インスタンスであることを確認
        assert manager1 is manager2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

"""Tests for VRM (3D) avatar support."""

import json
import struct
import tempfile
from pathlib import Path

import pytest

from backend.core.vrm import (
    EMOTION_TO_VRM_EXPRESSION,
    PHONEME_TO_VRM_VISEME,
    VRMController,
    VRMExpression,
    VRMExpressionPreset,
    VRMExpressionState,
    VRMLookAt,
    VRMMetadata,
    VRMModel,
    get_vrm_controller,
    parse_vrm_glb,
)


class TestVRMExpressionPreset:
    """Test VRM expression presets."""

    def test_emotion_presets_exist(self):
        """Ensure all emotion presets are defined."""
        assert VRMExpressionPreset.HAPPY.value == "happy"
        assert VRMExpressionPreset.SAD.value == "sad"
        assert VRMExpressionPreset.ANGRY.value == "angry"
        assert VRMExpressionPreset.SURPRISED.value == "surprised"
        assert VRMExpressionPreset.RELAXED.value == "relaxed"

    def test_viseme_presets_exist(self):
        """Ensure all viseme presets are defined."""
        assert VRMExpressionPreset.AA.value == "aa"
        assert VRMExpressionPreset.IH.value == "ih"
        assert VRMExpressionPreset.OU.value == "ou"
        assert VRMExpressionPreset.EE.value == "ee"
        assert VRMExpressionPreset.OH.value == "oh"

    def test_blink_presets_exist(self):
        """Ensure blink presets are defined."""
        assert VRMExpressionPreset.BLINK.value == "blink"
        assert VRMExpressionPreset.BLINK_LEFT.value == "blinkLeft"
        assert VRMExpressionPreset.BLINK_RIGHT.value == "blinkRight"


class TestVRMExpression:
    """Test VRM expression configuration."""

    def test_create_expression(self):
        """Test creating an expression."""
        expr = VRMExpression(
            name="happy",
            preset=VRMExpressionPreset.HAPPY,
            is_binary=False,
        )
        assert expr.name == "happy"
        assert expr.preset == VRMExpressionPreset.HAPPY
        assert not expr.is_binary

    def test_to_dict(self):
        """Test expression serialization."""
        expr = VRMExpression(
            name="test",
            preset=VRMExpressionPreset.SAD,
            is_binary=True,
            override_blink=True,
        )
        d = expr.to_dict()
        assert d["name"] == "test"
        assert d["preset"] == "sad"
        assert d["isBinary"] is True
        assert d["overrideBlink"] is True

    def test_no_preset(self):
        """Test expression without preset."""
        expr = VRMExpression(name="custom")
        d = expr.to_dict()
        assert d["preset"] is None


class TestVRMMetadata:
    """Test VRM metadata."""

    def test_default_values(self):
        """Test default metadata values."""
        meta = VRMMetadata()
        assert meta.title == ""
        assert meta.allowed_user_name == "Everyone"
        assert meta.violent_usage == "Disallow"

    def test_to_dict(self):
        """Test metadata serialization."""
        meta = VRMMetadata(
            title="Test Model",
            author="Test Author",
            version="1.0.0",
        )
        d = meta.to_dict()
        assert d["title"] == "Test Model"
        assert d["author"] == "Test Author"
        assert d["version"] == "1.0.0"


class TestVRMModel:
    """Test VRM model representation."""

    def test_create_model(self):
        """Test creating a model."""
        model = VRMModel(
            path=Path("/test/model.vrm"),
            vrm_version="0.0",
            metadata=VRMMetadata(title="Test"),
        )
        assert model.path == Path("/test/model.vrm")
        assert model.vrm_version == "0.0"
        assert model.metadata.title == "Test"

    def test_to_dict(self):
        """Test model serialization."""
        model = VRMModel(
            path=Path("/test/model.vrm"),
            vrm_version="1.0",
            expressions=[VRMExpression(name="happy", preset=VRMExpressionPreset.HAPPY)],
        )
        d = model.to_dict()
        assert d["path"] == "/test/model.vrm"
        assert d["vrmVersion"] == "1.0"
        assert len(d["expressions"]) == 1


class TestVRMExpressionState:
    """Test VRM expression state management."""

    def test_set_and_get(self):
        """Test setting and getting expression values."""
        state = VRMExpressionState()
        state.set("happy", 0.8)
        assert state.get("happy") == 0.8

    def test_value_clamping(self):
        """Test that values are clamped to 0-1 range."""
        state = VRMExpressionState()
        state.set("test", 1.5)
        assert state.get("test") == 1.0
        state.set("test", -0.5)
        assert state.get("test") == 0.0

    def test_default_value(self):
        """Test default value for unset expressions."""
        state = VRMExpressionState()
        assert state.get("unknown") == 0.0

    def test_reset(self):
        """Test resetting all expressions."""
        state = VRMExpressionState()
        state.set("happy", 1.0)
        state.set("sad", 0.5)
        state.reset()
        assert state.get("happy") == 0.0
        assert state.get("sad") == 0.0

    def test_to_dict(self):
        """Test state serialization."""
        state = VRMExpressionState()
        state.set("happy", 0.7)
        state.set("blink", 0.3)
        d = state.to_dict()
        assert d["happy"] == 0.7
        assert d["blink"] == 0.3


class TestVRMLookAt:
    """Test VRM look-at state."""

    def test_default_values(self):
        """Test default look-at values."""
        look_at = VRMLookAt()
        assert look_at.target_x == 0.0
        assert look_at.target_y == 0.0

    def test_to_dict(self):
        """Test look-at serialization."""
        look_at = VRMLookAt(target_x=0.5, target_y=-0.3)
        d = look_at.to_dict()
        assert d["targetX"] == 0.5
        assert d["targetY"] == -0.3


class TestVRMController:
    """Test VRM controller."""

    def test_initialization(self):
        """Test controller initialization."""
        ctrl = VRMController()
        assert ctrl.model is None
        assert ctrl.expression_state is not None

    def test_set_emotion_happy(self):
        """Test setting happy emotion."""
        ctrl = VRMController()
        result = ctrl.set_emotion("happy", 1.0)
        assert result["happy"] == 1.0

    def test_set_emotion_excited(self):
        """Test setting excited emotion (composite)."""
        ctrl = VRMController()
        result = ctrl.set_emotion("excited", 1.0)
        # Excited maps to happy with some surprised
        assert result["happy"] == 0.8
        assert result["surprised"] == 0.3

    def test_set_emotion_with_intensity(self):
        """Test emotion with intensity."""
        ctrl = VRMController()
        result = ctrl.set_emotion("sad", 0.5)
        assert result["sad"] == 0.5

    def test_set_emotion_resets_previous(self):
        """Test that setting emotion resets previous emotions."""
        ctrl = VRMController()
        ctrl.set_emotion("happy", 1.0)
        result = ctrl.set_emotion("sad", 1.0)
        assert result["happy"] == 0.0
        assert result["sad"] == 1.0

    def test_set_viseme_a(self):
        """Test setting viseme for 'a' phoneme."""
        ctrl = VRMController()
        result = ctrl.set_viseme("a", 1.0)
        assert result["aa"] == 1.0

    def test_set_viseme_all_japanese(self):
        """Test all Japanese vowel visemes."""
        ctrl = VRMController()
        for phoneme, preset in [("a", "aa"), ("i", "ih"), ("u", "ou"), ("e", "ee"), ("o", "oh")]:
            result = ctrl.set_viseme(phoneme, 0.8)
            assert result[preset] == 0.8

    def test_set_viseme_resets_previous(self):
        """Test that setting viseme resets previous visemes."""
        ctrl = VRMController()
        ctrl.set_viseme("a", 1.0)
        result = ctrl.set_viseme("i", 1.0)
        assert result["aa"] == 0.0
        assert result["ih"] == 1.0

    def test_blink(self):
        """Test blink trigger."""
        ctrl = VRMController()
        result = ctrl.blink()
        assert result["blink"] == 1.0

    def test_set_look_at(self):
        """Test setting look-at target."""
        ctrl = VRMController()
        result = ctrl.set_look_at(0.5, -0.3)
        assert result["targetX"] == 0.5
        assert result["targetY"] == -0.3

    def test_set_look_at_clamped(self):
        """Test look-at values are clamped."""
        ctrl = VRMController()
        result = ctrl.set_look_at(2.0, -2.0)
        assert result["targetX"] == 1.0
        assert result["targetY"] == -1.0

    def test_get_state(self):
        """Test getting full controller state."""
        ctrl = VRMController()
        ctrl.set_emotion("happy", 0.8)
        ctrl.set_look_at(0.2, 0.1)

        state = ctrl.get_state()
        assert "expressions" in state
        assert "lookAt" in state
        assert "boneRotations" in state
        assert state["expressions"]["happy"] == 0.8
        assert state["lookAt"]["targetX"] == 0.2

    def test_apply_emotion_from_text(self):
        """Test applying emotion from Lobby emotion engine."""
        ctrl = VRMController()
        state = ctrl.apply_emotion_from_text("surprised", 0.9)
        assert state["expressions"]["surprised"] == 0.9


class TestEmotionMapping:
    """Test emotion to VRM expression mapping."""

    def test_all_lobby_emotions_mapped(self):
        """Ensure all Lobby emotions have VRM mappings."""
        expected_emotions = ["happy", "excited", "sad", "angry", "surprised", "neutral", "relaxed"]
        for emotion in expected_emotions:
            assert emotion in EMOTION_TO_VRM_EXPRESSION


class TestPhonemeMapping:
    """Test phoneme to VRM viseme mapping."""

    def test_all_japanese_vowels_mapped(self):
        """Ensure all Japanese vowels have viseme mappings."""
        expected_phonemes = ["a", "i", "u", "e", "o", "n", "silence"]
        for phoneme in expected_phonemes:
            assert phoneme in PHONEME_TO_VRM_VISEME


class TestGetVRMController:
    """Test singleton controller accessor."""

    def test_singleton(self):
        """Test that get_vrm_controller returns singleton."""
        ctrl1 = get_vrm_controller()
        ctrl2 = get_vrm_controller()
        assert ctrl1 is ctrl2


class TestParseVRMGLB:
    """Test VRM GLB file parsing."""

    def _create_test_glb(self, vrm_extension: dict) -> Path:
        """Create a test GLB file with VRM extension."""
        # Minimal glTF JSON with VRM extension
        gltf_json = {
            "asset": {"version": "2.0"},
            "scene": 0,
            "scenes": [{"nodes": []}],
            "extensions": vrm_extension,
            "extensionsUsed": list(vrm_extension.keys()),
        }

        json_bytes = json.dumps(gltf_json).encode("utf-8")
        # Pad to 4-byte alignment
        while len(json_bytes) % 4 != 0:
            json_bytes += b" "

        # Build GLB
        glb = b"glTF"  # Magic
        glb += struct.pack("<I", 2)  # Version
        glb += struct.pack("<I", 12 + 8 + len(json_bytes))  # Total length
        glb += struct.pack("<I", len(json_bytes))  # JSON chunk length
        glb += b"JSON"  # JSON chunk type
        glb += json_bytes

        # Write to temp file
        with tempfile.NamedTemporaryFile(suffix=".vrm", delete=False) as f:
            f.write(glb)
            return Path(f.name)

    def test_parse_vrm_0x(self):
        """Test parsing VRM 0.x format."""
        vrm_ext = {
            "VRM": {
                "specVersion": "0.0",
                "meta": {
                    "title": "Test Model",
                    "author": "Test Author",
                    "version": "1.0",
                },
                "blendShapeMaster": {
                    "blendShapeGroups": [
                        {"name": "Happy", "presetName": "happy", "isBinary": False},
                        {"name": "Sad", "presetName": "sad", "isBinary": False},
                    ]
                }
            }
        }

        path = self._create_test_glb(vrm_ext)
        try:
            model = parse_vrm_glb(path)
            assert model.vrm_version == "0.0"
            assert model.metadata.title == "Test Model"
            assert model.metadata.author == "Test Author"
            assert len(model.expressions) == 2
            assert model.expressions[0].name == "Happy"
            assert model.expressions[0].preset == VRMExpressionPreset.HAPPY
        finally:
            path.unlink()

    def test_parse_vrm_1x(self):
        """Test parsing VRM 1.0 format."""
        vrm_ext = {
            "VRMC_vrm": {
                "specVersion": "1.0",
                "meta": {
                    "name": "Test Model 1.0",
                    "authors": ["Author A", "Author B"],
                    "version": "2.0",
                },
                "expressions": {
                    "preset": {
                        "happy": {"isBinary": False},
                        "angry": {"isBinary": False, "overrideBlink": "block"},
                    }
                }
            }
        }

        path = self._create_test_glb(vrm_ext)
        try:
            model = parse_vrm_glb(path)
            assert model.vrm_version == "1.0"
            assert model.metadata.title == "Test Model 1.0"
            assert model.metadata.author == "Author A, Author B"
            assert len(model.expressions) == 2
        finally:
            path.unlink()

    def test_invalid_file(self):
        """Test parsing invalid file."""
        with tempfile.NamedTemporaryFile(suffix=".vrm", delete=False) as f:
            f.write(b"invalid data")
            path = Path(f.name)

        try:
            with pytest.raises(ValueError, match="Invalid GLB file"):
                parse_vrm_glb(path)
        finally:
            path.unlink()

    def test_file_not_found(self):
        """Test loading non-existent file."""
        ctrl = VRMController()
        with pytest.raises(FileNotFoundError):
            ctrl.load_model(Path("/nonexistent/model.vrm"))

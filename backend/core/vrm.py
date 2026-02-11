"""
VRM (3D) Avatar Support for Lobby

VRM is a 3D avatar format based on glTF 2.0 optimized for VR/VTuber applications.
This module handles VRM model metadata and generates parameters for frontend rendering.

Supported VRM versions:
- VRM 0.x (vrm0)
- VRM 1.0 (vrmc_vrm)
"""

import json
import struct
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

# VRM BlendShape presets (Expression presets)
class VRMExpressionPreset(Enum):
    """Standard VRM expression presets."""
    # Emotion
    HAPPY = "happy"
    ANGRY = "angry"
    SAD = "sad"
    RELAXED = "relaxed"
    SURPRISED = "surprised"
    
    # Lip sync
    AA = "aa"  # あ
    IH = "ih"  # い
    OU = "ou"  # う
    EE = "ee"  # え
    OH = "oh"  # お
    
    # Eye
    BLINK = "blink"
    BLINK_LEFT = "blinkLeft"
    BLINK_RIGHT = "blinkRight"
    LOOK_UP = "lookUp"
    LOOK_DOWN = "lookDown"
    LOOK_LEFT = "lookLeft"
    LOOK_RIGHT = "lookRight"
    
    # Other
    NEUTRAL = "neutral"


@dataclass
class VRMExpression:
    """VRM expression/blend shape configuration."""
    name: str
    preset: VRMExpressionPreset | None = None
    is_binary: bool = False
    override_blink: bool = False
    override_look_at: bool = False
    override_mouth: bool = False
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "preset": self.preset.value if self.preset else None,
            "isBinary": self.is_binary,
            "overrideBlink": self.override_blink,
            "overrideLookAt": self.override_look_at,
            "overrideMouth": self.override_mouth,
        }


@dataclass
class VRMMetadata:
    """VRM model metadata."""
    title: str = ""
    version: str = ""
    author: str = ""
    contact_information: str = ""
    reference: str = ""
    allowed_user_name: str = "Everyone"
    violent_usage: str = "Disallow"
    sexual_usage: str = "Disallow"
    commercial_usage: str = "Disallow"
    license_name: str = ""
    other_license_url: str = ""
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "version": self.version,
            "author": self.author,
            "contactInformation": self.contact_information,
            "reference": self.reference,
            "allowedUserName": self.allowed_user_name,
            "violentUsage": self.violent_usage,
            "sexualUsage": self.sexual_usage,
            "commercialUsage": self.commercial_usage,
            "licenseName": self.license_name,
            "otherLicenseUrl": self.other_license_url,
        }


@dataclass
class VRMModel:
    """VRM model representation."""
    path: Path
    vrm_version: str = "0.0"
    metadata: VRMMetadata = field(default_factory=VRMMetadata)
    expressions: list[VRMExpression] = field(default_factory=list)
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "path": str(self.path),
            "vrmVersion": self.vrm_version,
            "metadata": self.metadata.to_dict(),
            "expressions": [e.to_dict() for e in self.expressions],
        }


@dataclass 
class VRMExpressionState:
    """Current state of VRM expressions."""
    values: dict[str, float] = field(default_factory=dict)
    
    def set(self, name: str, value: float) -> None:
        """Set expression value (0.0 to 1.0)."""
        self.values[name] = max(0.0, min(1.0, value))
    
    def get(self, name: str) -> float:
        """Get expression value."""
        return self.values.get(name, 0.0)
    
    def reset(self) -> None:
        """Reset all expressions to 0."""
        self.values.clear()
    
    def to_dict(self) -> dict[str, float]:
        return dict(self.values)


@dataclass
class VRMLookAt:
    """VRM look-at target state."""
    target_x: float = 0.0  # Left/Right (-1.0 to 1.0)
    target_y: float = 0.0  # Up/Down (-1.0 to 1.0)
    
    def to_dict(self) -> dict[str, float]:
        return {
            "targetX": self.target_x,
            "targetY": self.target_y,
        }


@dataclass
class VRMBoneRotation:
    """VRM bone rotation (quaternion)."""
    bone_name: str
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0
    w: float = 1.0
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "boneName": self.bone_name,
            "rotation": {"x": self.x, "y": self.y, "z": self.z, "w": self.w},
        }


# Mapping from Lobby emotion to VRM expressions
EMOTION_TO_VRM_EXPRESSION: dict[str, tuple[VRMExpressionPreset, float]] = {
    "happy": (VRMExpressionPreset.HAPPY, 1.0),
    "excited": (VRMExpressionPreset.HAPPY, 0.8),  # Happy with surprise
    "sad": (VRMExpressionPreset.SAD, 1.0),
    "angry": (VRMExpressionPreset.ANGRY, 1.0),
    "surprised": (VRMExpressionPreset.SURPRISED, 1.0),
    "neutral": (VRMExpressionPreset.NEUTRAL, 1.0),
    "relaxed": (VRMExpressionPreset.RELAXED, 1.0),
}

# Viseme mapping for Japanese phonemes
PHONEME_TO_VRM_VISEME: dict[str, VRMExpressionPreset] = {
    "a": VRMExpressionPreset.AA,
    "i": VRMExpressionPreset.IH,
    "u": VRMExpressionPreset.OU,
    "e": VRMExpressionPreset.EE,
    "o": VRMExpressionPreset.OH,
    "n": VRMExpressionPreset.NEUTRAL,
    "silence": VRMExpressionPreset.NEUTRAL,
}


def parse_vrm_glb(path: Path) -> VRMModel:
    """
    Parse VRM file (GLB format) and extract metadata.
    
    VRM files are glTF 2.0 binary format with VRM extensions.
    """
    with open(path, "rb") as f:
        # Read GLB header
        magic = f.read(4)
        if magic != b"glTF":
            raise ValueError(f"Invalid GLB file: {path}")
        
        version = struct.unpack("<I", f.read(4))[0]
        if version != 2:
            raise ValueError(f"Unsupported glTF version: {version}")
        
        _total_length = struct.unpack("<I", f.read(4))[0]
        
        # Read JSON chunk
        json_length = struct.unpack("<I", f.read(4))[0]
        json_type = f.read(4)
        if json_type != b"JSON":
            raise ValueError("First chunk must be JSON")
        
        json_data = f.read(json_length)
        gltf = json.loads(json_data.decode("utf-8"))
    
    return _parse_gltf_extensions(gltf, path)


def _parse_gltf_extensions(gltf: dict, path: Path) -> VRMModel:
    """Parse VRM extensions from glTF JSON."""
    extensions = gltf.get("extensions", {})
    
    # Check VRM version (0.x or 1.0)
    vrm_version = "0.0"
    metadata = VRMMetadata()
    expressions: list[VRMExpression] = []
    
    if "VRM" in extensions:
        # VRM 0.x format
        vrm = extensions["VRM"]
        vrm_version = vrm.get("specVersion", "0.0")
        
        # Parse metadata
        meta = vrm.get("meta", {})
        metadata = VRMMetadata(
            title=meta.get("title", ""),
            version=meta.get("version", ""),
            author=meta.get("author", ""),
            contact_information=meta.get("contactInformation", ""),
            reference=meta.get("reference", ""),
            allowed_user_name=meta.get("allowedUserName", "Everyone"),
            violent_usage=meta.get("violentUssageName", "Disallow"),
            sexual_usage=meta.get("sexualUssageName", "Disallow"),
            commercial_usage=meta.get("commercialUssageName", "Disallow"),
            license_name=meta.get("licenseName", ""),
            other_license_url=meta.get("otherLicenseUrl", ""),
        )
        
        # Parse blend shapes
        blend_shape_master = vrm.get("blendShapeMaster", {})
        for group in blend_shape_master.get("blendShapeGroups", []):
            preset_str = group.get("presetName", "").lower()
            preset = None
            for p in VRMExpressionPreset:
                if p.value.lower() == preset_str:
                    preset = p
                    break
            
            expressions.append(VRMExpression(
                name=group.get("name", ""),
                preset=preset,
                is_binary=group.get("isBinary", False),
            ))
    
    elif "VRMC_vrm" in extensions:
        # VRM 1.0 format
        vrmc = extensions["VRMC_vrm"]
        vrm_version = "1.0"
        
        # Parse metadata
        meta = vrmc.get("meta", {})
        metadata = VRMMetadata(
            title=meta.get("name", ""),
            version=meta.get("version", ""),
            author=", ".join(meta.get("authors", [])),
            contact_information=meta.get("contactInformation", ""),
            reference=", ".join(meta.get("references", [])),
            allowed_user_name=meta.get("avatarPermission", "everyone"),
            commercial_usage=meta.get("commercialUsage", "personalNonProfit"),
            license_name=meta.get("licenseUrl", ""),
        )
        
        # Parse expressions
        vrmc_expressions = vrmc.get("expressions", {})
        for preset_name, expr_data in vrmc_expressions.get("preset", {}).items():
            preset = None
            for p in VRMExpressionPreset:
                if p.value.lower() == preset_name.lower():
                    preset = p
                    break
            
            expressions.append(VRMExpression(
                name=preset_name,
                preset=preset,
                is_binary=expr_data.get("isBinary", False),
                override_blink=expr_data.get("overrideBlink") == "block",
                override_look_at=expr_data.get("overrideLookAt") == "block",
                override_mouth=expr_data.get("overrideMouth") == "block",
            ))
    
    return VRMModel(
        path=path,
        vrm_version=vrm_version,
        metadata=metadata,
        expressions=expressions,
    )


class VRMController:
    """
    VRM avatar controller for Lobby.
    
    Manages VRM model state and generates parameters for frontend rendering.
    """
    
    def __init__(self, model_path: Path | None = None):
        self.model: VRMModel | None = None
        self.expression_state = VRMExpressionState()
        self.look_at = VRMLookAt()
        self.bone_rotations: list[VRMBoneRotation] = []
        self._blink_timer: float = 0.0
        self._auto_blink_enabled: bool = True
        
        if model_path:
            self.load_model(model_path)
    
    def load_model(self, path: Path) -> VRMModel:
        """Load VRM model from file."""
        if not path.exists():
            raise FileNotFoundError(f"VRM file not found: {path}")
        
        self.model = parse_vrm_glb(path)
        self.expression_state.reset()
        return self.model
    
    def set_emotion(self, emotion: str, intensity: float = 1.0) -> dict[str, float]:
        """
        Set emotion expression.
        
        Returns expression values to apply.
        """
        # Reset emotion expressions first
        for preset_name in ["happy", "sad", "angry", "surprised", "relaxed", "neutral"]:
            self.expression_state.set(preset_name, 0.0)
        
        # Apply new emotion
        if emotion in EMOTION_TO_VRM_EXPRESSION:
            preset, base_intensity = EMOTION_TO_VRM_EXPRESSION[emotion]
            final_intensity = base_intensity * intensity
            self.expression_state.set(preset.value, final_intensity)
            
            # Add secondary expressions for some emotions
            if emotion == "excited":
                self.expression_state.set(VRMExpressionPreset.SURPRISED.value, 0.3 * intensity)
        
        return self.expression_state.to_dict()
    
    def set_viseme(self, phoneme: str, intensity: float = 1.0) -> dict[str, float]:
        """
        Set viseme (lip sync) for phoneme.
        
        Returns expression values to apply.
        """
        # Reset all visemes first
        for viseme in ["aa", "ih", "ou", "ee", "oh"]:
            self.expression_state.set(viseme, 0.0)
        
        # Apply new viseme
        if phoneme in PHONEME_TO_VRM_VISEME:
            preset = PHONEME_TO_VRM_VISEME[phoneme]
            if preset != VRMExpressionPreset.NEUTRAL:
                self.expression_state.set(preset.value, intensity)
        
        return self.expression_state.to_dict()
    
    def blink(self) -> dict[str, float]:
        """Trigger a blink animation."""
        self.expression_state.set(VRMExpressionPreset.BLINK.value, 1.0)
        return self.expression_state.to_dict()
    
    def set_look_at(self, x: float, y: float) -> dict[str, float]:
        """
        Set look-at target.
        
        Args:
            x: Horizontal direction (-1.0 = left, 1.0 = right)
            y: Vertical direction (-1.0 = down, 1.0 = up)
        """
        self.look_at.target_x = max(-1.0, min(1.0, x))
        self.look_at.target_y = max(-1.0, min(1.0, y))
        return self.look_at.to_dict()
    
    def update(self, delta_time: float) -> dict[str, Any]:
        """
        Update controller state (call each frame).
        
        Handles auto-blink and other automated behaviors.
        
        Returns current state for frontend.
        """
        import random
        
        # Auto blink
        if self._auto_blink_enabled:
            self._blink_timer += delta_time
            
            # Random blink every 3-5 seconds
            if self._blink_timer > random.uniform(3.0, 5.0):
                self._blink_timer = 0.0
                # Start blink (frontend should animate this)
                self.expression_state.set(VRMExpressionPreset.BLINK.value, 1.0)
            elif self.expression_state.get(VRMExpressionPreset.BLINK.value) > 0:
                # Decay blink
                current = self.expression_state.get(VRMExpressionPreset.BLINK.value)
                self.expression_state.set(VRMExpressionPreset.BLINK.value, max(0, current - delta_time * 10))
        
        return self.get_state()
    
    def get_state(self) -> dict[str, Any]:
        """Get current controller state for frontend."""
        return {
            "expressions": self.expression_state.to_dict(),
            "lookAt": self.look_at.to_dict(),
            "boneRotations": [r.to_dict() for r in self.bone_rotations],
        }
    
    def apply_emotion_from_text(self, emotion: str, intensity: float = 1.0) -> dict[str, Any]:
        """
        Apply emotion based on Lobby emotion engine output.
        
        Maps Lobby emotions to VRM expressions.
        """
        self.set_emotion(emotion, intensity)
        return self.get_state()


# Singleton controller instance
_vrm_controller: VRMController | None = None


def get_vrm_controller() -> VRMController:
    """Get global VRM controller instance."""
    global _vrm_controller
    if _vrm_controller is None:
        _vrm_controller = VRMController()
    return _vrm_controller

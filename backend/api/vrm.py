"""
VRM (3D Avatar) REST API for Lobby

Provides endpoints for controlling VRM avatar state:
- Model management (load/info)
- Expression control (emotions, visemes)
- Look-at control
- Full state retrieval
"""

from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from backend.core.vrm import (
    get_vrm_controller,
)

router = APIRouter(prefix="/vrm", tags=["vrm"])


# Request/Response Models

class LoadModelRequest(BaseModel):
    """Request to load a VRM model."""
    path: str = Field(..., description="Path to VRM file")


class LoadModelResponse(BaseModel):
    """Response after loading a model."""
    model_config = ConfigDict(populate_by_name=True)

    success: bool
    vrm_version: str = Field(alias="vrmVersion")
    title: str
    author: str
    expression_count: int = Field(alias="expressionCount")


class SetEmotionRequest(BaseModel):
    """Request to set emotion expression."""
    emotion: str = Field(..., description="Emotion name (happy, sad, angry, etc.)")
    intensity: float = Field(default=1.0, ge=0.0, le=1.0, description="Emotion intensity")


class SetVisemeRequest(BaseModel):
    """Request to set viseme (lip sync)."""
    phoneme: str = Field(..., description="Phoneme (a, i, u, e, o, n, silence)")
    intensity: float = Field(default=1.0, ge=0.0, le=1.0, description="Viseme intensity")


class SetLookAtRequest(BaseModel):
    """Request to set look-at target."""
    x: float = Field(..., ge=-1.0, le=1.0, description="Horizontal direction (-1=left, 1=right)")
    y: float = Field(..., ge=-1.0, le=1.0, description="Vertical direction (-1=down, 1=up)")


class ExpressionStateResponse(BaseModel):
    """Response with expression values."""
    expressions: dict[str, float]


class LookAtResponse(BaseModel):
    """Response with look-at state."""
    model_config = ConfigDict(populate_by_name=True)

    target_x: float = Field(alias="targetX")
    target_y: float = Field(alias="targetY")


class VRMStateResponse(BaseModel):
    """Full VRM state response."""
    model_config = ConfigDict(populate_by_name=True)

    expressions: dict[str, float]
    look_at: dict[str, float] = Field(alias="lookAt")
    bone_rotations: list[dict[str, Any]] = Field(alias="boneRotations")


class ModelInfoResponse(BaseModel):
    """VRM model information response."""
    model_config = ConfigDict(populate_by_name=True)

    loaded: bool
    path: str | None = None
    vrm_version: str | None = Field(default=None, alias="vrmVersion")
    title: str | None = None
    author: str | None = None
    expressions: list[str] = []


class AvailablePresetsResponse(BaseModel):
    """Available VRM expression presets."""
    emotions: list[str]
    visemes: list[str]
    eye: list[str]
    other: list[str]


# API Endpoints

@router.get("/status")
async def get_status() -> dict[str, bool]:
    """Check if VRM controller is available."""
    return {"available": True}


@router.post("/load", response_model=LoadModelResponse)
async def load_model(request: LoadModelRequest) -> LoadModelResponse:
    """
    Load a VRM model from file.

    The model will be parsed and its metadata/expressions extracted.
    The frontend should load the same file for Three.js rendering.
    """
    path = Path(request.path)
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"VRM file not found: {path}")

    if path.suffix.lower() not in (".vrm", ".glb"):
        raise HTTPException(status_code=400, detail="File must be .vrm or .glb format")

    try:
        ctrl = get_vrm_controller()
        model = ctrl.load_model(path)
        return LoadModelResponse(
            success=True,
            vrmVersion=model.vrm_version,
            title=model.metadata.title,
            author=model.metadata.author,
            expressionCount=len(model.expressions),
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/model", response_model=ModelInfoResponse)
async def get_model_info() -> ModelInfoResponse:
    """Get information about the currently loaded model."""
    ctrl = get_vrm_controller()

    if ctrl.model is None:
        return ModelInfoResponse(loaded=False)

    return ModelInfoResponse(
        loaded=True,
        path=str(ctrl.model.path),
        vrmVersion=ctrl.model.vrm_version,
        title=ctrl.model.metadata.title,
        author=ctrl.model.metadata.author,
        expressions=[e.name for e in ctrl.model.expressions],
    )


@router.post("/emotion", response_model=ExpressionStateResponse)
async def set_emotion(request: SetEmotionRequest) -> ExpressionStateResponse:
    """
    Set emotion expression.

    Supported emotions: happy, excited, sad, angry, surprised, neutral, relaxed
    """
    ctrl = get_vrm_controller()
    expressions = ctrl.set_emotion(request.emotion, request.intensity)
    return ExpressionStateResponse(expressions=expressions)


@router.post("/viseme", response_model=ExpressionStateResponse)
async def set_viseme(request: SetVisemeRequest) -> ExpressionStateResponse:
    """
    Set viseme (lip sync) for phoneme.

    Supported phonemes: a, i, u, e, o, n, silence (Japanese vowels)
    """
    ctrl = get_vrm_controller()
    expressions = ctrl.set_viseme(request.phoneme, request.intensity)
    return ExpressionStateResponse(expressions=expressions)


@router.post("/blink", response_model=ExpressionStateResponse)
async def trigger_blink() -> ExpressionStateResponse:
    """Trigger a blink animation."""
    ctrl = get_vrm_controller()
    expressions = ctrl.blink()
    return ExpressionStateResponse(expressions=expressions)


@router.post("/look-at", response_model=LookAtResponse)
async def set_look_at(request: SetLookAtRequest) -> LookAtResponse:
    """
    Set look-at target direction.

    - x: Horizontal (-1.0 = left, 1.0 = right)
    - y: Vertical (-1.0 = down, 1.0 = up)
    """
    ctrl = get_vrm_controller()
    result = ctrl.set_look_at(request.x, request.y)
    return LookAtResponse(targetX=result["targetX"], targetY=result["targetY"])


@router.get("/state", response_model=VRMStateResponse)
async def get_state() -> VRMStateResponse:
    """Get current VRM controller state (expressions, look-at, bones)."""
    ctrl = get_vrm_controller()
    state = ctrl.get_state()
    return VRMStateResponse(
        expressions=state["expressions"],
        lookAt=state["lookAt"],
        boneRotations=state["boneRotations"],
    )


@router.post("/reset")
async def reset_state() -> dict[str, bool]:
    """Reset all expressions and look-at to default."""
    ctrl = get_vrm_controller()
    ctrl.expression_state.reset()
    ctrl.look_at.target_x = 0.0
    ctrl.look_at.target_y = 0.0
    return {"success": True}


@router.get("/presets", response_model=AvailablePresetsResponse)
async def get_available_presets() -> AvailablePresetsResponse:
    """Get list of available VRM expression presets."""
    return AvailablePresetsResponse(
        emotions=["happy", "angry", "sad", "relaxed", "surprised", "neutral"],
        visemes=["aa", "ih", "ou", "ee", "oh"],
        eye=["blink", "blinkLeft", "blinkRight", "lookUp", "lookDown", "lookLeft", "lookRight"],
        other=["neutral"],
    )

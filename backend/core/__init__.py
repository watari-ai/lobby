"""Core modules for Lobby"""

from .avatar import (
    AvatarFrame,
    AvatarParts,
    AvatarRenderer,
    Expression,
    LipsyncAnalyzer,
    LipsyncConfig,
    MouthShape,
)
from .emotion import Emotion, EmotionAnalyzer
from .live2d import (
    Live2DConfig,
    Live2DExpression,
    Live2DFrame,
    Live2DLipsyncAnalyzer,
    Live2DModel,
    Live2DParameters,
)
from .pipeline import (
    LineResult,
    PipelineConfig,
    RecordingPipeline,
    quick_record,
)
from .tts import TTSClient, TTSConfig
from .video import VideoComposer, VideoConfig, get_audio_duration_ms
from .openclaw import OpenClawClient, OpenClawConfig, LOBBY_SYSTEM_PROMPT

__all__ = [
    # TTS
    "TTSClient",
    "TTSConfig",
    # Emotion
    "EmotionAnalyzer",
    "Emotion",
    # Avatar (PNG)
    "MouthShape",
    "Expression",
    "AvatarFrame",
    "AvatarParts",
    "LipsyncConfig",
    "LipsyncAnalyzer",
    "AvatarRenderer",
    # Avatar (Live2D)
    "Live2DConfig",
    "Live2DExpression",
    "Live2DFrame",
    "Live2DLipsyncAnalyzer",
    "Live2DModel",
    "Live2DParameters",
    # Video
    "VideoComposer",
    "VideoConfig",
    "get_audio_duration_ms",
    # Pipeline
    "PipelineConfig",
    "LineResult",
    "RecordingPipeline",
    "quick_record",
    # OpenClaw
    "OpenClawClient",
    "OpenClawConfig",
    "LOBBY_SYSTEM_PROMPT",
]

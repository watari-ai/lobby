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
from .emotion import Emotion, EmotionAnalyzer, EmotionResult
from .live2d import (
    Live2DConfig,
    Live2DExpression,
    Live2DFrame,
    Live2DLipsyncAnalyzer,
    Live2DModel,
    Live2DParameters,
)
from .tts import TTSClient, TTSConfig
from .video import VideoComposer, VideoConfig, get_audio_duration_ms
from .openclaw import OpenClawClient, OpenClawConfig, LOBBY_SYSTEM_PROMPT
from .audio_manager import (
    AudioChannel,
    AudioManager,
    AudioTrack,
    EMOTION_SE_MAPPING,
    PlaybackState,
    RepeatMode,
    SoundEffect,
)


# Pipeline は循環参照を避けるため遅延インポート
def _import_pipeline():
    from .pipeline import (
        LineResult,
        PipelineConfig,
        RecordingPipeline,
        quick_record,
    )
    return LineResult, PipelineConfig, RecordingPipeline, quick_record


# 遅延インポートされるシンボル
LineResult = None
PipelineConfig = None
RecordingPipeline = None
quick_record = None


def __getattr__(name):
    """遅延インポート対応"""
    global LineResult, PipelineConfig, RecordingPipeline, quick_record
    if name in ("LineResult", "PipelineConfig", "RecordingPipeline", "quick_record"):
        if LineResult is None:
            LineResult, PipelineConfig, RecordingPipeline, quick_record = _import_pipeline()
        return {"LineResult": LineResult, "PipelineConfig": PipelineConfig,
                "RecordingPipeline": RecordingPipeline, "quick_record": quick_record}[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

__all__ = [
    # TTS
    "TTSClient",
    "TTSConfig",
    # Emotion
    "EmotionAnalyzer",
    "EmotionResult",
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
    # Pipeline (lazy import)
    "PipelineConfig",
    "LineResult",
    "RecordingPipeline",
    "quick_record",
    # OpenClaw
    "OpenClawClient",
    "OpenClawConfig",
    "LOBBY_SYSTEM_PROMPT",
    # Audio Manager
    "AudioChannel",
    "AudioManager",
    "AudioTrack",
    "EMOTION_SE_MAPPING",
    "PlaybackState",
    "RepeatMode",
    "SoundEffect",
]

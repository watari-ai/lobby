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
from .pipeline import (
    LineResult,
    PipelineConfig,
    RecordingPipeline,
    quick_record,
)
from .tts import TTSClient, TTSConfig
from .video import VideoComposer, VideoConfig, get_audio_duration_ms

__all__ = [
    # TTS
    "TTSClient",
    "TTSConfig",
    # Emotion
    "EmotionAnalyzer",
    "Emotion",
    # Avatar
    "MouthShape",
    "Expression",
    "AvatarFrame",
    "AvatarParts",
    "LipsyncConfig",
    "LipsyncAnalyzer",
    "AvatarRenderer",
    # Video
    "VideoComposer",
    "VideoConfig",
    "get_audio_duration_ms",
    # Pipeline
    "PipelineConfig",
    "LineResult",
    "RecordingPipeline",
    "quick_record",
]

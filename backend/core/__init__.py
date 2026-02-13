"""Core modules for Lobby"""

from .audio_manager import (
    EMOTION_SE_MAPPING,
    AudioChannel,
    AudioManager,
    AudioTrack,
    PlaybackState,
    RepeatMode,
    SoundEffect,
)
from .avatar import (
    AvatarFrame,
    AvatarParts,
    AvatarRenderer,
    Expression,
    LipsyncAnalyzer,
    LipsyncConfig,
    MouthShape,
)
from .clip import (
    ClipConfig,
    ClipExtractor,
    ClipManager,
    ClipResult,
)
from .emotion import Emotion, EmotionAnalyzer, EmotionResult
from .highlight import (
    Highlight,
    HighlightConfig,
    HighlightDetector,
    HighlightEnabledRecorder,
    HighlightType,
)
from .live2d import (
    Live2DConfig,
    Live2DExpression,
    Live2DFrame,
    Live2DLipsyncAnalyzer,
    Live2DModel,
    Live2DParameters,
)
from .openclaw import LOBBY_SYSTEM_PROMPT, OpenClawClient, OpenClawConfig
from .scene import (
    Background,
    CameraAngle,
    CameraSettings,
    Overlay,
    OverlayType,
    Scene,
    SceneManager,
    get_scene_manager,
)
from .subtitle import (
    SubtitleEntry,
    SubtitleFormat,
    SubtitleGenerator,
    SubtitleTrack,
    generate_subtitles_from_recording,
)
from .subtitle_translator import (
    LANGUAGE_NAMES,
    SubtitleTranslator,
    TranslationProvider,
    TranslationResult,
    TranslatorConfig,
    translate_subtitle_file,
)
from .thumbnail import (
    FrameQuality,
    ThumbnailConfig,
    ThumbnailGenerator,
    ThumbnailManager,
    ThumbnailResult,
    ThumbnailSize,
)
from .tts import TTSClient, TTSConfig
from .video import VideoComposer, VideoConfig, get_audio_duration_ms
from .vrm import (
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
    # Scene Manager
    "Background",
    "CameraAngle",
    "CameraSettings",
    "Overlay",
    "OverlayType",
    "Scene",
    "SceneManager",
    "get_scene_manager",
    # VRM (3D)
    "EMOTION_TO_VRM_EXPRESSION",
    "PHONEME_TO_VRM_VISEME",
    "VRMController",
    "VRMExpression",
    "VRMExpressionPreset",
    "VRMExpressionState",
    "VRMLookAt",
    "VRMMetadata",
    "VRMModel",
    "get_vrm_controller",
    "parse_vrm_glb",
    # Subtitle
    "SubtitleEntry",
    "SubtitleFormat",
    "SubtitleGenerator",
    "SubtitleTrack",
    "generate_subtitles_from_recording",
    # Subtitle Translation
    "LANGUAGE_NAMES",
    "SubtitleTranslator",
    "TranslationProvider",
    "TranslationResult",
    "TranslatorConfig",
    "translate_subtitle_file",
    # Highlight Detection
    "Highlight",
    "HighlightConfig",
    "HighlightDetector",
    "HighlightEnabledRecorder",
    "HighlightType",
    # Clip Extraction
    "ClipConfig",
    "ClipExtractor",
    "ClipManager",
    "ClipResult",
    # Thumbnail Generation
    "FrameQuality",
    "ThumbnailConfig",
    "ThumbnailGenerator",
    "ThumbnailManager",
    "ThumbnailResult",
    "ThumbnailSize",
]

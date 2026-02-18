"""Config Loader - lobby.yaml 統合設定読み込み"""

from dataclasses import field
from pathlib import Path
from typing import Optional

import yaml
from loguru import logger

from .avatar import AvatarParts, LipsyncConfig
from .pipeline import BGMConfig, PipelineConfig, SubtitleConfig
from .tts import TTSConfig
from .video import VideoConfig

DEFAULT_CONFIG_PATH = Path("config/lobby.yaml")


def load_config(path: Optional[Path] = None) -> dict:
    """YAML設定ファイルを読み込み

    Args:
        path: 設定ファイルパス（省略時は config/lobby.yaml）

    Returns:
        設定辞書
    """
    config_path = path or DEFAULT_CONFIG_PATH
    if not config_path.exists():
        logger.warning(f"Config not found: {config_path}, using defaults")
        return {}

    with config_path.open(encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    logger.info(f"Loaded config: {config_path}")
    return data


def build_tts_config(data: dict) -> TTSConfig:
    """設定辞書からTTSConfig を生成"""
    tts = data.get("tts", {})
    return TTSConfig(
        provider=tts.get("provider", "miotts"),
        base_url=tts.get("base_url", "http://localhost:8001"),
        voice=tts.get("voice", "lobby"),
        model=tts.get("model", ""),
        response_format=tts.get("response_format", "base64"),
        emotion_prompts=tts.get("emotion_prompts"),
    )


def build_avatar_parts(data: dict) -> AvatarParts:
    """設定辞書からAvatarPartsを生成"""
    avatar = data.get("avatar", {})

    def _path(key: str) -> Optional[Path]:
        val = avatar.get(key, "")
        return Path(val) if val else None

    base = _path("base")
    mouth_closed = _path("mouth_closed")

    if not base or not mouth_closed:
        raise ValueError("avatar.base and avatar.mouth_closed are required in config")

    return AvatarParts(
        base=base,
        mouth_closed=mouth_closed,
        mouth_open_s=_path("mouth_open_s"),
        mouth_open_m=_path("mouth_open_m"),
        mouth_open_l=_path("mouth_open_l"),
        eyes_open=_path("eyes_open"),
        eyes_closed=_path("eyes_closed"),
    )


def build_lipsync_config(data: dict) -> LipsyncConfig:
    """設定辞書からLipsyncConfigを生成"""
    ls = data.get("lipsync", {})
    return LipsyncConfig(
        fps=ls.get("fps", 30),
        mouth_sensitivity=ls.get("mouth_sensitivity", 0.5),
        blink_interval_ms=ls.get("blink_interval_ms", 3000),
        blink_duration_ms=ls.get("blink_duration_ms", 150),
    )


def build_video_config(data: dict) -> VideoConfig:
    """設定辞書からVideoConfigを生成"""
    v = data.get("video", {})
    return VideoConfig(
        fps=v.get("fps", 30),
        width=v.get("width", 1920),
        height=v.get("height", 1080),
        codec=v.get("codec", "libx264"),
        crf=v.get("crf", 23),
        preset=v.get("preset", "medium"),
    )


def build_subtitle_config(data: dict) -> SubtitleConfig:
    """設定辞書からSubtitleConfigを生成"""
    from .subtitle import SubtitleFormat

    s = data.get("subtitle", {})
    formats = []
    for fmt_str in s.get("formats", ["srt"]):
        try:
            formats.append(SubtitleFormat(fmt_str))
        except ValueError:
            logger.warning(f"Unknown subtitle format: {fmt_str}")

    return SubtitleConfig(
        enabled=s.get("enabled", True),
        burn_in=s.get("burn_in", False),
        formats=formats or [SubtitleFormat.SRT],
        font_size=s.get("font_size", 48),
        font_name=s.get("font_name", "Noto Sans CJK JP"),
        margin_bottom=s.get("margin_bottom", 60),
        outline_width=s.get("outline_width", 3),
    )


def build_bgm_config(data: dict) -> BGMConfig:
    """設定辞書からBGMConfigを生成"""
    b = data.get("bgm", {})
    path = b.get("path")
    return BGMConfig(
        enabled=b.get("enabled", bool(path)),
        path=Path(path) if path else None,
        volume=b.get("volume", 0.15),
        duck_volume=b.get("duck_volume", 0.08),
        fade_in_ms=b.get("fade_in_ms", 2000),
        fade_out_ms=b.get("fade_out_ms", 3000),
    )


def build_pipeline_config(
    data: dict,
    avatar_parts: Optional[AvatarParts] = None,
) -> PipelineConfig:
    """設定辞書からPipelineConfigを生成

    Args:
        data: 設定辞書
        avatar_parts: AvatarParts（省略時は設定から生成）

    Returns:
        PipelineConfig
    """
    parts = avatar_parts or build_avatar_parts(data)
    output_dir = Path(data.get("output_dir", "./output"))

    return PipelineConfig(
        tts=build_tts_config(data),
        lipsync=build_lipsync_config(data),
        video=build_video_config(data),
        avatar_parts=parts,
        output_dir=output_dir,
        subtitle=build_subtitle_config(data),
        bgm=build_bgm_config(data),
    )

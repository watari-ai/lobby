"""Tests for Recording Pipeline - subtitle integration"""

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.core.pipeline import (
    LineResult,
    PipelineConfig,
    RecordingPipeline,
    SubtitleConfig,
)
from backend.core.avatar import AvatarParts, LipsyncConfig
from backend.core.emotion import Emotion
from backend.core.subtitle import SubtitleFormat
from backend.core.tts import TTSConfig
from backend.core.video import VideoConfig
from backend.modes.recording import Script, ScriptLine


@pytest.fixture
def avatar_parts(tmp_path):
    """テスト用アバターパーツ"""
    base = tmp_path / "base.png"
    mouth = tmp_path / "mouth_closed.png"
    base.write_bytes(b"fake")
    mouth.write_bytes(b"fake")
    return AvatarParts(base=base, mouth_closed=mouth)


@pytest.fixture
def pipeline_config(avatar_parts, tmp_path):
    """テスト用パイプライン設定"""
    return PipelineConfig(
        tts=TTSConfig(),
        lipsync=LipsyncConfig(),
        video=VideoConfig(),
        avatar_parts=avatar_parts,
        output_dir=tmp_path / "output",
        subtitle=SubtitleConfig(enabled=True, formats=[SubtitleFormat.SRT]),
    )


class TestSubtitleConfig:
    """SubtitleConfig テスト"""

    def test_default(self):
        config = SubtitleConfig()
        assert config.enabled is True
        assert config.burn_in is False
        assert SubtitleFormat.SRT in config.formats
        assert config.font_size == 48

    def test_custom(self):
        config = SubtitleConfig(
            burn_in=True,
            speaker="ロビィ",
            font_size=36,
        )
        assert config.burn_in is True
        assert config.speaker == "ロビィ"
        assert config.font_size == 36


class TestPipelineSubtitleGeneration:
    """パイプラインの字幕生成テスト"""

    def test_generate_subtitles_basic(self, pipeline_config, tmp_path):
        """基本的な字幕生成"""
        pipeline = RecordingPipeline(pipeline_config)
        work_dir = tmp_path / "work"
        work_dir.mkdir()

        results = [
            LineResult(
                line=ScriptLine(text="おはロビィ！", emotion=Emotion.HAPPY, wait_after=0.5),
                audio_path=tmp_path / "0000.mp3",
                frames_dir=tmp_path / "frames" / "0000",
                frame_count=30,
                duration_ms=1500,
            ),
            LineResult(
                line=ScriptLine(text="今日もがんばるっす！", emotion=Emotion.EXCITED, wait_after=0.3),
                audio_path=tmp_path / "0001.mp3",
                frames_dir=tmp_path / "frames" / "0001",
                frame_count=45,
                duration_ms=2000,
            ),
        ]

        subtitle_paths = pipeline._generate_subtitles(results, work_dir, "Test")

        assert SubtitleFormat.SRT in subtitle_paths
        srt_path = subtitle_paths[SubtitleFormat.SRT]
        assert srt_path.exists()

        content = srt_path.read_text()
        assert "おはロビィ！" in content
        assert "今日もがんばるっす！" in content
        assert "00:00:00,000" in content  # first entry starts at 0

    def test_generate_subtitles_multiple_formats(self, pipeline_config, tmp_path):
        """SRT + VTT両方生成"""
        pipeline_config.subtitle.formats = [SubtitleFormat.SRT, SubtitleFormat.VTT]
        pipeline = RecordingPipeline(pipeline_config)
        work_dir = tmp_path / "work"
        work_dir.mkdir()

        results = [
            LineResult(
                line=ScriptLine(text="テスト", emotion=Emotion.NEUTRAL),
                audio_path=tmp_path / "0000.mp3",
                frames_dir=tmp_path / "frames" / "0000",
                frame_count=30,
                duration_ms=1000,
            ),
        ]

        subtitle_paths = pipeline._generate_subtitles(results, work_dir, "Test")

        assert SubtitleFormat.SRT in subtitle_paths
        assert SubtitleFormat.VTT in subtitle_paths
        assert subtitle_paths[SubtitleFormat.SRT].exists()
        assert subtitle_paths[SubtitleFormat.VTT].exists()

    def test_generate_subtitles_with_speaker(self, pipeline_config, tmp_path):
        """話者名付き字幕"""
        pipeline_config.subtitle.speaker = "ロビィ"
        pipeline_config.subtitle.formats = [SubtitleFormat.VTT]
        pipeline = RecordingPipeline(pipeline_config)
        work_dir = tmp_path / "work"
        work_dir.mkdir()

        results = [
            LineResult(
                line=ScriptLine(text="やっほー！", emotion=Emotion.HAPPY),
                audio_path=tmp_path / "0000.mp3",
                frames_dir=tmp_path / "frames" / "0000",
                frame_count=30,
                duration_ms=1000,
            ),
        ]

        subtitle_paths = pipeline._generate_subtitles(results, work_dir, "Test")
        vtt_content = subtitle_paths[SubtitleFormat.VTT].read_text()
        assert "ロビィ" in vtt_content

    def test_generate_subtitles_timing(self, pipeline_config, tmp_path):
        """字幕タイミングが正しいか"""
        pipeline = RecordingPipeline(pipeline_config)
        work_dir = tmp_path / "work"
        work_dir.mkdir()

        results = [
            LineResult(
                line=ScriptLine(text="最初の行", emotion=Emotion.NEUTRAL, wait_after=1.0),
                audio_path=tmp_path / "0000.mp3",
                frames_dir=tmp_path / "frames" / "0000",
                frame_count=30,
                duration_ms=2000,
            ),
            LineResult(
                line=ScriptLine(text="次の行", emotion=Emotion.NEUTRAL, wait_after=0.5),
                audio_path=tmp_path / "0001.mp3",
                frames_dir=tmp_path / "frames" / "0001",
                frame_count=30,
                duration_ms=1500,
            ),
        ]

        subtitle_paths = pipeline._generate_subtitles(results, work_dir, "Test")
        content = subtitle_paths[SubtitleFormat.SRT].read_text()

        # 1行目: 0ms ~ 2000ms
        assert "00:00:00,000 --> 00:00:02,000" in content
        # 2行目: 2000 + 1000(wait) + 200(gap) = 3200ms ~ 4700ms
        assert "00:00:03,200 --> 00:00:04,700" in content

    def test_disabled_subtitles(self, pipeline_config, tmp_path):
        """字幕無効時"""
        pipeline_config.subtitle.enabled = False
        pipeline = RecordingPipeline(pipeline_config)
        # _generate_subtitles is not called when disabled (tested via process_script)
        # Just verify config
        assert pipeline.config.subtitle.enabled is False


class TestPipelineConfigDefault:
    """PipelineConfig.default テスト"""

    def test_default_has_subtitle_config(self, avatar_parts):
        config = PipelineConfig.default(avatar_parts)
        assert config.subtitle.enabled is True
        assert config.subtitle.burn_in is False

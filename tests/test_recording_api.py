"""Tests for Recording API routes."""

import json
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from backend.api.recording import (
    RecordingRequest,
    TTSSettings,
    AvatarSettings,
    VideoSettings,
    ScriptInfo,
    _parse_script,
    _build_avatar_parts,
)
from backend.modes.recording import Script
from backend.core.avatar import AvatarParts
from backend.core.emotion import Emotion


class TestParseScript:
    """Test script parsing from request."""

    def test_parse_from_text(self):
        req = RecordingRequest(
            script_text="おはロビィ！\n[excited] マジっすか！",
            avatar=AvatarSettings(base="/tmp/base.png", mouth_closed="/tmp/mouth.png"),
        )
        script = _parse_script(req)
        assert script.title == "Untitled"
        assert len(script.lines) == 2

    def test_parse_from_json(self):
        script_json = json.dumps({
            "title": "テスト台本",
            "scenes": [
                {"lines": [{"text": "こんにちは", "emotion": "happy"}]}
            ],
        })
        req = RecordingRequest(
            script_json=script_json,
            avatar=AvatarSettings(base="/tmp/base.png", mouth_closed="/tmp/mouth.png"),
        )
        script = _parse_script(req)
        assert script.title == "テスト台本"
        assert len(script.lines) == 1
        assert script.lines[0].emotion == Emotion.HAPPY

    def test_parse_no_input_raises(self):
        req = RecordingRequest(
            avatar=AvatarSettings(base="/tmp/base.png", mouth_closed="/tmp/mouth.png"),
        )
        with pytest.raises(Exception):  # HTTPException
            _parse_script(req)

    def test_parse_from_path_not_found(self):
        req = RecordingRequest(
            script_path="/nonexistent/file.txt",
            avatar=AvatarSettings(base="/tmp/base.png", mouth_closed="/tmp/mouth.png"),
        )
        with pytest.raises(Exception):
            _parse_script(req)


class TestBuildAvatarParts:
    """Test avatar parts construction."""

    def test_minimal(self):
        settings = AvatarSettings(base="/tmp/base.png", mouth_closed="/tmp/mouth.png")
        parts = _build_avatar_parts(settings)
        assert parts.base.name == "base.png"
        assert parts.mouth_closed.name == "mouth.png"
        assert parts.mouth_open_s is None

    def test_full(self):
        settings = AvatarSettings(
            base="/tmp/base.png",
            mouth_closed="/tmp/mc.png",
            mouth_open_s="/tmp/ms.png",
            mouth_open_m="/tmp/mm.png",
            mouth_open_l="/tmp/ml.png",
            eyes_open="/tmp/eo.png",
            eyes_closed="/tmp/ec.png",
        )
        parts = _build_avatar_parts(settings)
        assert parts.mouth_open_s is not None
        assert parts.eyes_closed is not None


class TestModels:
    """Test Pydantic models."""

    def test_tts_settings_defaults(self):
        s = TTSSettings()
        assert s.provider == "miotts"
        assert s.voice == "lobby"

    def test_video_settings_defaults(self):
        v = VideoSettings()
        assert v.fps == 30
        assert v.width == 1920

    def test_recording_request_minimal(self):
        req = RecordingRequest(
            script_text="テスト",
            avatar=AvatarSettings(base="/b.png", mouth_closed="/m.png"),
        )
        assert req.tts.provider == "miotts"
        assert req.video.fps == 30

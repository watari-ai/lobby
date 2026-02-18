"""Tests for config loader."""

import tempfile
from pathlib import Path

import pytest
import yaml

from backend.core.config import (
    build_avatar_parts,
    build_lipsync_config,
    build_pipeline_config,
    build_subtitle_config,
    build_tts_config,
    build_video_config,
    load_config,
)


@pytest.fixture
def sample_config():
    return {
        "server": {"host": "0.0.0.0", "port": 8100},
        "tts": {
            "provider": "miotts",
            "base_url": "http://localhost:8001",
            "voice": "lobby",
        },
        "avatar": {
            "base": "/tmp/base.png",
            "mouth_closed": "/tmp/mouth_closed.png",
            "mouth_open_s": "/tmp/mouth_s.png",
        },
        "lipsync": {"fps": 24, "mouth_sensitivity": 0.7},
        "video": {"fps": 24, "width": 1280, "height": 720, "crf": 18},
        "subtitle": {"enabled": True, "burn_in": True, "formats": ["srt", "vtt"]},
        "output_dir": "./output",
    }


@pytest.fixture
def config_file(sample_config):
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        yaml.dump(sample_config, f)
        return Path(f.name)


def test_load_config(config_file):
    data = load_config(config_file)
    assert data["server"]["port"] == 8100
    assert data["tts"]["provider"] == "miotts"


def test_load_config_missing():
    data = load_config(Path("/nonexistent/config.yaml"))
    assert data == {}


def test_build_tts_config(sample_config):
    cfg = build_tts_config(sample_config)
    assert cfg.provider == "miotts"
    assert cfg.base_url == "http://localhost:8001"
    assert cfg.voice == "lobby"


def test_build_tts_config_defaults():
    cfg = build_tts_config({})
    assert cfg.provider == "miotts"
    assert cfg.voice == "lobby"


def test_build_avatar_parts(sample_config):
    parts = build_avatar_parts(sample_config)
    assert parts.base == Path("/tmp/base.png")
    assert parts.mouth_closed == Path("/tmp/mouth_closed.png")
    assert parts.mouth_open_s == Path("/tmp/mouth_s.png")
    assert parts.mouth_open_m is None


def test_build_avatar_parts_missing_required():
    with pytest.raises(ValueError, match="required"):
        build_avatar_parts({"avatar": {"base": "/tmp/base.png"}})


def test_build_lipsync_config(sample_config):
    cfg = build_lipsync_config(sample_config)
    assert cfg.fps == 24
    assert cfg.mouth_sensitivity == 0.7


def test_build_video_config(sample_config):
    cfg = build_video_config(sample_config)
    assert cfg.fps == 24
    assert cfg.width == 1280
    assert cfg.height == 720
    assert cfg.crf == 18


def test_build_subtitle_config(sample_config):
    cfg = build_subtitle_config(sample_config)
    assert cfg.enabled is True
    assert cfg.burn_in is True
    assert len(cfg.formats) == 2


def test_build_pipeline_config(sample_config):
    from backend.core.avatar import AvatarParts

    parts = AvatarParts(
        base=Path("/tmp/base.png"),
        mouth_closed=Path("/tmp/mouth.png"),
    )
    cfg = build_pipeline_config(sample_config, avatar_parts=parts)
    assert cfg.tts.provider == "miotts"
    assert cfg.video.fps == 24
    assert cfg.output_dir == Path("./output")

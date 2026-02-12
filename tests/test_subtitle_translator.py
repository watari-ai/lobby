"""Tests for Subtitle Translator"""

import pytest
from pathlib import Path

from backend.core.subtitle import SubtitleTrack, SubtitleFormat
from backend.core.subtitle_translator import (
    SubtitleTranslator,
    TranslatorConfig,
    TranslationProvider,
    LANGUAGE_NAMES,
    _parse_srt,
    _parse_vtt,
    _srt_time_to_ms,
    _vtt_time_to_ms,
)


class TestTimeConversion:
    """タイムスタンプ変換テスト"""

    def test_srt_time_to_ms(self):
        """SRTタイムスタンプ変換"""
        assert _srt_time_to_ms("00:00:01,000") == 1000
        assert _srt_time_to_ms("00:01:30,500") == 90500
        assert _srt_time_to_ms("01:00:00,000") == 3600000

    def test_vtt_time_to_ms(self):
        """VTTタイムスタンプ変換"""
        assert _vtt_time_to_ms("00:01.000") == 1000
        assert _vtt_time_to_ms("01:30.500") == 90500
        assert _vtt_time_to_ms("01:00:00.000") == 3600000


class TestSubtitleParsing:
    """字幕パーステスト"""

    def test_parse_srt(self):
        """SRTパース"""
        content = """1
00:00:01,000 --> 00:00:03,000
Hello world

2
00:00:04,000 --> 00:00:06,000
This is a test
"""
        track = SubtitleTrack()
        result = _parse_srt(content, track)
        
        assert len(result.entries) == 2
        assert result.entries[0].text == "Hello world"
        assert result.entries[0].start_ms == 1000
        assert result.entries[0].end_ms == 3000
        assert result.entries[1].text == "This is a test"

    def test_parse_vtt(self):
        """VTTパース"""
        content = """WEBVTT
Language: ja

00:01.000 --> 00:03.000
こんにちは

00:04.000 --> 00:06.000
テストです
"""
        track = SubtitleTrack()
        result = _parse_vtt(content, track)
        
        assert result.language == "ja"
        assert len(result.entries) == 2
        assert result.entries[0].text == "こんにちは"


class TestLanguageNames:
    """言語名テスト"""

    def test_language_mapping(self):
        """言語コードマッピング"""
        assert LANGUAGE_NAMES["ja"] == "Japanese"
        assert LANGUAGE_NAMES["en"] == "English"
        assert LANGUAGE_NAMES["zh"] == "Chinese"
        assert LANGUAGE_NAMES["ko"] == "Korean"


class TestTranslatorConfig:
    """翻訳設定テスト"""

    def test_default_config(self):
        """デフォルト設定"""
        config = TranslatorConfig()
        
        assert config.provider == TranslationProvider.OPENCLAW
        assert config.openclaw_url == "http://localhost:18789"
        assert config.batch_size == 10
        assert config.context_lines == 2


class TestSubtitleTranslator:
    """字幕翻訳器テスト"""

    def test_translator_init(self):
        """翻訳器初期化"""
        translator = SubtitleTranslator()
        
        assert translator.config.provider == TranslationProvider.OPENCLAW
    
    def test_clean_translation(self):
        """翻訳結果クリーニング"""
        translator = SubtitleTranslator()
        
        # 引用符除去
        assert translator._clean_translation('"Hello"') == "Hello"
        assert translator._clean_translation("'Hello'") == "Hello"
        
        # プレフィックス除去
        assert translator._clean_translation("Translation: Hello") == "Hello"
        assert translator._clean_translation("[Translation] Hello") == "Hello"

    def test_get_language_name(self):
        """言語名取得"""
        translator = SubtitleTranslator()
        
        assert translator._get_language_name("ja") == "Japanese"
        assert translator._get_language_name("en") == "English"
        assert translator._get_language_name("unknown") == "unknown"


class TestSubtitleTrackTranslation:
    """字幕トラック翻訳テスト（モック）"""

    @pytest.fixture
    def sample_track(self):
        """サンプルトラック"""
        track = SubtitleTrack(language="ja", title="Test")
        track.add_entry("おはようございます", start_ms=0, end_ms=2000)
        track.add_entry("今日もいい天気ですね", start_ms=2500, end_ms=5000)
        track.add_entry("ありがとうございます", start_ms=5500, end_ms=7500)
        return track

    def test_track_structure(self, sample_track):
        """トラック構造確認"""
        assert len(sample_track.entries) == 3
        assert sample_track.language == "ja"
        assert sample_track.title == "Test"
        
        # タイミング確認
        assert sample_track.entries[0].start_ms == 0
        assert sample_track.entries[2].end_ms == 7500


# Integration test (requires OpenClaw Gateway)
@pytest.mark.skip(reason="Requires running OpenClaw Gateway")
class TestTranslatorIntegration:
    """統合テスト（OpenClaw Gateway必要）"""

    @pytest.mark.asyncio
    async def test_translate_text(self):
        """テキスト翻訳"""
        translator = SubtitleTranslator()
        
        result = await translator.translate_text(
            text="こんにちは",
            source_lang="ja",
            target_lang="en",
        )
        
        assert result.original == "こんにちは"
        assert result.target_lang == "en"
        # 翻訳結果は環境依存
        
        await translator.close()

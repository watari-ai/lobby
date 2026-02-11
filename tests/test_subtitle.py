"""Tests for Subtitle Generator"""

import pytest
from pathlib import Path
from unittest.mock import patch, AsyncMock

from backend.core.subtitle import (
    SubtitleEntry,
    SubtitleTrack,
    SubtitleFormat,
    SubtitleGenerator,
    generate_subtitles_from_recording,
)


class TestSubtitleEntry:
    """SubtitleEntry テスト"""

    def test_ms_to_srt(self):
        """SRT形式タイムスタンプ変換テスト"""
        entry = SubtitleEntry(
            index=1,
            start_ms=0,
            end_ms=1000,
            text="テスト"
        )
        assert entry.start_srt == "00:00:00,000"
        assert entry.end_srt == "00:00:01,000"

    def test_ms_to_srt_complex(self):
        """複雑なタイムスタンプ変換テスト"""
        entry = SubtitleEntry(
            index=1,
            start_ms=3661234,  # 1時間1分1秒234ミリ秒
            end_ms=3665678,
            text="テスト"
        )
        assert entry.start_srt == "01:01:01,234"
        assert entry.end_srt == "01:01:05,678"

    def test_ms_to_vtt(self):
        """VTT形式タイムスタンプ変換テスト"""
        entry = SubtitleEntry(
            index=1,
            start_ms=1500,
            end_ms=3750,
            text="テスト"
        )
        # VTTはドット区切り
        assert entry.start_vtt == "00:00:01.500"
        assert entry.end_vtt == "00:00:03.750"

    def test_to_srt(self):
        """SRT形式出力テスト"""
        entry = SubtitleEntry(
            index=1,
            start_ms=0,
            end_ms=2000,
            text="おはロビィ！"
        )
        expected = "1\n00:00:00,000 --> 00:00:02,000\nおはロビィ！\n"
        assert entry.to_srt() == expected

    def test_to_vtt(self):
        """VTT形式出力テスト"""
        entry = SubtitleEntry(
            index=1,
            start_ms=0,
            end_ms=2000,
            text="おはロビィ！"
        )
        expected = "00:00:00.000 --> 00:00:02.000\nおはロビィ！\n"
        assert entry.to_vtt() == expected

    def test_to_vtt_with_speaker(self):
        """話者付きVTT形式出力テスト"""
        entry = SubtitleEntry(
            index=1,
            start_ms=0,
            end_ms=2000,
            text="おはロビィ！",
            speaker="ロビィ"
        )
        result = entry.to_vtt()
        assert "<v ロビィ>" in result
        assert "おはロビィ！" in result


class TestSubtitleTrack:
    """SubtitleTrack テスト"""

    def test_add_entry(self):
        """エントリー追加テスト"""
        track = SubtitleTrack()
        entry = track.add_entry(
            text="テスト1",
            start_ms=0,
            end_ms=1000,
        )
        assert entry.index == 1
        assert len(track.entries) == 1

        entry2 = track.add_entry(
            text="テスト2",
            start_ms=1000,
            end_ms=2000,
        )
        assert entry2.index == 2
        assert len(track.entries) == 2

    def test_to_srt(self):
        """SRT出力テスト"""
        track = SubtitleTrack()
        track.add_entry("行1", 0, 1000)
        track.add_entry("行2", 1000, 2000)

        srt = track.to_srt()
        assert "1\n00:00:00,000 --> 00:00:01,000\n行1\n" in srt
        assert "2\n00:00:01,000 --> 00:00:02,000\n行2\n" in srt

    def test_to_vtt(self):
        """VTT出力テスト"""
        track = SubtitleTrack(title="テスト字幕", language="ja")
        track.add_entry("行1", 0, 1000)

        vtt = track.to_vtt()
        assert "WEBVTT" in vtt
        assert "Title: テスト字幕" in vtt
        assert "Language: ja" in vtt
        assert "00:00:00.000 --> 00:00:01.000" in vtt
        assert "行1" in vtt

    def test_save_srt(self, tmp_path):
        """SRTファイル保存テスト"""
        track = SubtitleTrack()
        track.add_entry("テスト", 0, 1000)

        output_path = tmp_path / "test.srt"
        saved_path = track.save(output_path, SubtitleFormat.SRT)

        assert saved_path.exists()
        content = saved_path.read_text(encoding="utf-8")
        assert "1\n00:00:00,000 --> 00:00:01,000\nテスト\n" in content

    def test_save_vtt(self, tmp_path):
        """VTTファイル保存テスト"""
        track = SubtitleTrack(language="ja")
        track.add_entry("テスト", 0, 1000)

        output_path = tmp_path / "test.vtt"
        saved_path = track.save(output_path, SubtitleFormat.VTT)

        assert saved_path.exists()
        content = saved_path.read_text(encoding="utf-8")
        assert "WEBVTT" in content
        assert "テスト" in content


class TestSubtitleGenerator:
    """SubtitleGenerator テスト"""

    def test_create_track(self):
        """トラック作成テスト"""
        generator = SubtitleGenerator(language="ja")
        track = generator.create_track("テスト")

        assert track.title == "テスト"
        assert track.language == "ja"

    def test_generate_from_segments(self):
        """セグメントから字幕生成テスト"""
        generator = SubtitleGenerator(speaker="ロビィ")

        segments = [
            {"text": "おはロビィ！", "duration_ms": 2000},
            {"text": "僕、倉土ロビィっす！", "duration_ms": 3000},
        ]

        track = generator.generate_from_segments(segments, title="自己紹介")

        assert track.title == "自己紹介"
        assert len(track.entries) == 2
        assert track.entries[0].text == "おはロビィ！"
        assert track.entries[0].start_ms == 0
        assert track.entries[0].end_ms == 2000
        assert track.entries[1].start_ms == 2100  # gap_ms=100

    def test_split_text_short(self):
        """短いテキスト分割テスト（分割なし）"""
        generator = SubtitleGenerator()
        lines = generator._split_text("短いテキスト")
        assert lines == ["短いテキスト"]

    def test_split_text_long(self):
        """長いテキスト分割テスト"""
        generator = SubtitleGenerator()
        long_text = "これは非常に長いテキストです。句読点で適切に分割されることを確認するためのテストです。"
        lines = generator._split_text(long_text, max_chars=30)

        assert len(lines) >= 2
        for line in lines:
            assert len(line) <= 35  # 多少のオーバーは許容

    def test_split_text_with_punctuation(self):
        """句読点での分割テスト"""
        generator = SubtitleGenerator()
        text = "これはテストです。次の文章に続きます。"
        lines = generator._split_text(text, max_chars=15)

        # 句点で分割されるはず
        assert "です。" in lines[0] or any("です。" in line for line in lines)


class TestGenerateSubtitlesFromRecording:
    """generate_subtitles_from_recording テスト"""

    @pytest.mark.asyncio
    async def test_generate_subtitles(self, tmp_path):
        """収録結果からの字幕生成テスト"""
        # モックの RecordingResult
        class MockLine:
            def __init__(self, text, wait_after=0.5):
                self.text = text
                self.wait_after = wait_after

        class MockResult:
            def __init__(self, text, audio_path, duration_ms):
                self.line = MockLine(text)
                self.audio_path = audio_path
                self.duration_ms = duration_ms

        # テスト用のダミー音声ファイル
        audio1 = tmp_path / "audio1.mp3"
        audio2 = tmp_path / "audio2.mp3"
        audio1.touch()
        audio2.touch()

        results = [
            MockResult("おはロビィ！", audio1, 2000),
            MockResult("僕、倉土ロビィっす！", audio2, 3000),
        ]

        # get_audio_duration_ms をモック
        # ffprobeがない環境でも動くようにフォールバック値を使用
        # (実際のテストでは音声ファイルが空なのでduration_msのフォールバックが使われる)
        output_paths = await generate_subtitles_from_recording(
            results=results,
            output_dir=tmp_path,
            title="Test Recording",
            speaker="ロビィ",
        )

        # SRT と VTT の両方が生成される
        assert SubtitleFormat.SRT in output_paths
        assert SubtitleFormat.VTT in output_paths

        # ファイルが存在する
        assert output_paths[SubtitleFormat.SRT].exists()
        assert output_paths[SubtitleFormat.VTT].exists()

        # 内容を確認
        srt_content = output_paths[SubtitleFormat.SRT].read_text(encoding="utf-8")
        assert "おはロビィ！" in srt_content
        assert "僕、倉土ロビィっす！" in srt_content

        vtt_content = output_paths[SubtitleFormat.VTT].read_text(encoding="utf-8")
        assert "WEBVTT" in vtt_content
        assert "<v ロビィ>" in vtt_content

    @pytest.mark.asyncio
    async def test_generate_subtitles_single_format(self, tmp_path):
        """単一フォーマットでの生成テスト"""
        class MockLine:
            text = "テスト"
            wait_after = 0.5

        class MockResult:
            line = MockLine()
            audio_path = tmp_path / "test.mp3"
            duration_ms = 1000

        MockResult.audio_path.touch()

        # ffprobeがない環境でも動くようにフォールバック値を使用
        output_paths = await generate_subtitles_from_recording(
            results=[MockResult()],
            output_dir=tmp_path,
            title="Test",
            formats=[SubtitleFormat.SRT],
        )

        # SRT のみ生成
        assert SubtitleFormat.SRT in output_paths
        assert SubtitleFormat.VTT not in output_paths


class TestEdgeCases:
    """エッジケーステスト"""

    def test_empty_text(self):
        """空テキストの処理"""
        generator = SubtitleGenerator()
        segments = [
            {"text": "", "duration_ms": 1000},
            {"text": "テスト", "duration_ms": 1000},
        ]
        track = generator.generate_from_segments(segments)

        # 空テキストはスキップされる
        assert len(track.entries) == 1
        assert track.entries[0].text == "テスト"

    def test_zero_duration(self):
        """ゼロ長の処理"""
        track = SubtitleTrack()
        track.add_entry("テスト", 0, 0)

        # タイムスタンプは同じになる
        srt = track.to_srt()
        assert "00:00:00,000 --> 00:00:00,000" in srt

    def test_multiline_text(self):
        """複数行テキストの処理"""
        entry = SubtitleEntry(
            index=1,
            start_ms=0,
            end_ms=3000,
            text="行1\n行2\n行3"
        )
        srt = entry.to_srt()
        assert "行1\n行2\n行3" in srt

    def test_special_characters(self):
        """特殊文字の処理"""
        track = SubtitleTrack()
        track.add_entry("絵文字🦞とか<html>タグとか", 0, 1000)

        srt = track.to_srt()
        assert "🦞" in srt
        assert "<html>" in srt

        vtt = track.to_vtt()
        assert "🦞" in vtt

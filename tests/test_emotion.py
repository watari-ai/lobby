"""Emotion Analyzer Tests"""

import pytest
from backend.core.emotion import EmotionAnalyzer, Emotion


class TestEmotionAnalyzer:
    def setup_method(self):
        self.analyzer = EmotionAnalyzer()
    
    def test_explicit_tag_happy(self):
        result = self.analyzer.analyze("[happy] 今日はいい天気っすね！")
        assert result.primary == Emotion.HAPPY
        assert result.raw_text == "今日はいい天気っすね！"
    
    def test_explicit_tag_excited(self):
        result = self.analyzer.analyze("[excited] マジでやばいっす！")
        assert result.primary == Emotion.EXCITED
        assert result.raw_text == "マジでやばいっす！"
    
    def test_explicit_tag_sad(self):
        result = self.analyzer.analyze("[sad] ちょっと寂しかったっすね...")
        assert result.primary == Emotion.SAD
    
    def test_keyword_excited(self):
        result = self.analyzer.analyze("マジっすか！やばいっすね！！")
        assert result.primary == Emotion.EXCITED
    
    def test_keyword_sad(self):
        result = self.analyzer.analyze("なんだか寂しいっす...")
        assert result.primary == Emotion.SAD
    
    def test_neutral_default(self):
        result = self.analyzer.analyze("今日は水曜日っす")
        assert result.primary == Emotion.NEUTRAL
    
    def test_intensity_tag_higher(self):
        result = self.analyzer.analyze("[happy] テスト")
        assert result.intensity >= 0.7
    
    def test_invalid_tag_ignored(self):
        result = self.analyzer.analyze("[invalid] テスト")
        # Invalid tags should fall back to keyword analysis
        assert result.raw_text == "テスト"

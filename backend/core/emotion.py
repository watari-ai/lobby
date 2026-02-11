"""Emotion Analyzer - テキストから感情を分析"""

import re
from dataclasses import dataclass
from enum import Enum
from typing import Optional


class Emotion(str, Enum):
    """感情タイプ"""
    HAPPY = "happy"
    SAD = "sad"
    EXCITED = "excited"
    ANGRY = "angry"
    SURPRISED = "surprised"
    NEUTRAL = "neutral"


@dataclass
class EmotionResult:
    """感情分析結果"""
    primary: Emotion
    intensity: float  # 0.0 - 1.0
    secondary: Optional[Emotion] = None
    raw_text: str = ""  # 感情タグを除いたテキスト


class EmotionAnalyzer:
    """ルールベース感情分析器"""

    # 感情タグパターン: [happy], [sad], etc.
    TAG_PATTERN = re.compile(r'\[(\w+)\]\s*')

    # キーワードマッピング
    EMOTION_KEYWORDS: dict[Emotion, list[str]] = {
        Emotion.HAPPY: ["嬉しい", "楽しい", "やった", "！", "♪", "😊", "😄", "w", "笑"],
        Emotion.SAD: ["悲しい", "寂しい", "辛い", "泣", "😢", "😭", "..."],
        Emotion.EXCITED: ["すごい", "やばい", "マジ", "！！", "！？", "🔥", "✨", "っす！"],
        Emotion.ANGRY: ["怒", "ムカ", "許さ", "💢", "😠"],
        Emotion.SURPRISED: ["え？", "えっ", "びっくり", "驚", "!?", "？！", "😮", "😲"],
    }

    def analyze(self, text: str) -> EmotionResult:
        """テキストから感情を分析

        1. 明示的な感情タグ [happy] などがあればそれを使用
        2. なければキーワードベースで分析
        3. どちらもなければ neutral
        """
        # 1. タグをチェック
        tag_match = self.TAG_PATTERN.match(text)
        if tag_match:
            tag = tag_match.group(1).lower()
            raw_text = self.TAG_PATTERN.sub("", text)

            try:
                emotion = Emotion(tag)
                return EmotionResult(
                    primary=emotion,
                    intensity=0.8,  # タグ指定は高い確信度
                    raw_text=raw_text,
                )
            except ValueError:
                # 無効なタグは無視
                pass

        # 2. キーワードベース分析
        raw_text = self.TAG_PATTERN.sub("", text)
        scores: dict[Emotion, float] = {e: 0.0 for e in Emotion}

        for emotion, keywords in self.EMOTION_KEYWORDS.items():
            for keyword in keywords:
                if keyword in text:
                    scores[emotion] += 0.3

        # 句読点パターン
        if text.count("！") >= 2:
            scores[Emotion.EXCITED] += 0.3
        if text.count("...") >= 1:
            scores[Emotion.SAD] += 0.2

        # 最高スコアを見つける
        max_score = max(scores.values())
        if max_score > 0:
            primary = max(scores, key=lambda e: scores[e])
            # 二番目の感情
            sorted_emotions = sorted(scores.items(), key=lambda x: x[1], reverse=True)
            secondary = sorted_emotions[1][0] if sorted_emotions[1][1] > 0 else None

            return EmotionResult(
                primary=primary,
                intensity=min(max_score, 1.0),
                secondary=secondary,
                raw_text=raw_text,
            )

        # 3. デフォルト
        return EmotionResult(
            primary=Emotion.NEUTRAL,
            intensity=0.5,
            raw_text=raw_text,
        )

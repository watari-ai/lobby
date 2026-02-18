"""Recording Mode - 台本ベースの収録モード"""

import asyncio
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import AsyncGenerator, Optional

from loguru import logger

from ..core.emotion import Emotion, EmotionAnalyzer
from ..core.tts import TTSClient, TTSConfig
from ..core.video import get_audio_duration_ms


@dataclass
class ScriptLine:
    """台本の1行"""
    text: str
    emotion: Emotion = Emotion.NEUTRAL
    wait_after: float = 0.5  # 次の行までの待機時間（秒）
    gesture: Optional[str] = None  # アバター用ジェスチャー

    @classmethod
    def from_dict(cls, data: dict) -> "ScriptLine":
        """辞書から生成"""
        emotion = data.get("emotion", "neutral")
        if isinstance(emotion, str):
            try:
                emotion = Emotion(emotion)
            except ValueError:
                emotion = Emotion.NEUTRAL

        return cls(
            text=data["text"],
            emotion=emotion,
            wait_after=data.get("wait_after", 0.5),
            gesture=data.get("gesture"),
        )


@dataclass
class Script:
    """台本"""
    title: str
    lines: list[ScriptLine] = field(default_factory=list)

    @classmethod
    def from_text(cls, content: str, title: str = "Untitled") -> "Script":
        """プレーンテキストからパース

        フォーマット:
            おはロビィ！僕、倉土ロビィっす！
            [excited] マジでびっくりしたっす！
            [sad] ちょっと寂しかったっすね...
        """
        analyzer = EmotionAnalyzer()
        lines = []

        for line in content.strip().split("\n"):
            line = line.strip()
            if not line:
                continue

            result = analyzer.analyze(line)
            lines.append(ScriptLine(
                text=result.raw_text or line,
                emotion=result.primary,
            ))

        return cls(title=title, lines=lines)

    @classmethod
    def from_json(cls, content: str) -> "Script":
        """JSONからパース

        フォーマット:
        {
            "title": "台本タイトル",
            "scenes": [
                {
                    "id": "intro",
                    "lines": [
                        {"text": "...", "emotion": "happy", "gesture": "wave"}
                    ]
                }
            ]
        }
        """
        data = json.loads(content)
        lines = []

        for scene in data.get("scenes", []):
            for line_data in scene.get("lines", []):
                lines.append(ScriptLine.from_dict(line_data))

        return cls(
            title=data.get("title", "Untitled"),
            lines=lines,
        )

    @classmethod
    def from_file(cls, path: Path) -> "Script":
        """ファイルから読み込み"""
        content = path.read_text(encoding="utf-8")

        if path.suffix == ".json":
            return cls.from_json(content)
        else:
            return cls.from_text(content, title=path.stem)


@dataclass
class RecordingResult:
    """収録結果"""
    line: ScriptLine
    audio_path: Path
    duration_ms: int = 0


class RecordingMode:
    """収録モード"""

    def __init__(
        self,
        tts_config: TTSConfig | None = None,
        output_dir: Path | None = None,
    ):
        self.tts_config = tts_config or TTSConfig()
        self.output_dir = output_dir or Path("./output")
        self._tts_client: TTSClient | None = None

    async def _get_tts(self) -> TTSClient:
        """TTSクライアントを取得（遅延初期化）"""
        if self._tts_client is None:
            self._tts_client = TTSClient(self.tts_config)
        return self._tts_client

    async def record_script(
        self,
        script: Script,
        progress_callback: Optional[callable] = None,
    ) -> AsyncGenerator[RecordingResult, None]:
        """台本を収録

        Args:
            script: 収録する台本
            progress_callback: 進捗コールバック (current, total) -> None

        Yields:
            RecordingResult: 各行の収録結果
        """
        tts = await self._get_tts()
        total = len(script.lines)
        audio_dir = self.output_dir / script.title.replace(" ", "_")
        audio_dir.mkdir(parents=True, exist_ok=True)

        logger.info(f"Recording script: {script.title} ({total} lines)")

        for i, line in enumerate(script.lines, 1):
            if progress_callback:
                progress_callback(i, total)

            audio_path = audio_dir / f"{i:04d}.mp3"

            logger.info(f"[{i}/{total}] {line.text[:30]}... ({line.emotion.value})")

            try:
                audio_data = await tts.synthesize(
                    text=line.text,
                    emotion=line.emotion.value,
                    output_path=audio_path,
                )

                # ffprobeで正確な長さを取得
                duration_ms = await get_audio_duration_ms(audio_path)
                if duration_ms <= 0:
                    # フォールバック: バイト数からの概算
                    duration_ms = int(len(audio_data) / 32)

                yield RecordingResult(
                    line=line,
                    audio_path=audio_path,
                    duration_ms=duration_ms,
                )

            except Exception as e:
                logger.error(f"Failed to synthesize line {i}: {e}")
                raise

            # 次の行までの待機
            if line.wait_after > 0:
                await asyncio.sleep(line.wait_after)

        logger.info(f"Recording complete: {audio_dir}")

    async def close(self):
        """リソースを解放"""
        if self._tts_client:
            await self._tts_client.close()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

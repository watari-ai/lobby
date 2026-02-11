"""Recording Pipeline - 収録ワークフロー統合"""

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

from loguru import logger

from ..modes.recording import Script, ScriptLine
from .avatar import (
    AvatarParts,
    AvatarRenderer,
    Expression,
    LipsyncAnalyzer,
    LipsyncConfig,
)
from .emotion import Emotion
from .tts import TTSClient, TTSConfig
from .video import VideoComposer, VideoConfig, get_audio_duration_ms


@dataclass
class PipelineConfig:
    """パイプライン設定"""
    tts: TTSConfig
    lipsync: LipsyncConfig
    video: VideoConfig
    avatar_parts: AvatarParts
    output_dir: Path = Path("./output")
    background_image: Optional[Path] = None

    @classmethod
    def default(cls, avatar_parts: AvatarParts) -> "PipelineConfig":
        """デフォルト設定で生成"""
        return cls(
            tts=TTSConfig(),
            lipsync=LipsyncConfig(),
            video=VideoConfig(),
            avatar_parts=avatar_parts,
        )


@dataclass
class LineResult:
    """1行の処理結果"""
    line: ScriptLine
    audio_path: Path
    frames_dir: Path
    frame_count: int
    duration_ms: int


class RecordingPipeline:
    """収録パイプライン

    台本 → TTS → リップシンク解析 → フレームレンダリング → 動画出力
    """

    def __init__(self, config: PipelineConfig):
        self.config = config
        self._tts = TTSClient(config.tts)
        self._lipsync = LipsyncAnalyzer(config.lipsync)
        self._renderer = AvatarRenderer(config.avatar_parts)
        self._composer = VideoComposer(config.video)

    async def process_line(
        self,
        line: ScriptLine,
        line_index: int,
        work_dir: Path,
    ) -> LineResult:
        """1行を処理

        Args:
            line: 台本の行
            line_index: 行番号（0始まり）
            work_dir: 作業ディレクトリ

        Returns:
            LineResult
        """
        prefix = f"{line_index:04d}"
        audio_path = work_dir / "audio" / f"{prefix}.mp3"
        frames_dir = work_dir / "frames" / prefix

        # 1. TTS生成
        logger.info(f"[{line_index}] TTS: {line.text[:30]}...")
        await self._tts.synthesize(
            text=line.text,
            emotion=line.emotion.value,
            output_path=audio_path,
        )

        # 2. リップシンク解析
        logger.info(f"[{line_index}] Lipsync analysis...")
        frames = self._lipsync.analyze_audio(audio_path)

        # 感情を表情に変換
        expression = self._emotion_to_expression(line.emotion)
        for frame in frames:
            frame.expression = expression

        # 3. フレームレンダリング
        logger.info(f"[{line_index}] Rendering {len(frames)} frames...")
        self._renderer.render_animation(
            frames=frames,
            output_dir=frames_dir,
        )

        # 音声の長さを取得
        duration_ms = await get_audio_duration_ms(audio_path)

        return LineResult(
            line=line,
            audio_path=audio_path,
            frames_dir=frames_dir,
            frame_count=len(frames),
            duration_ms=duration_ms,
        )

    def _emotion_to_expression(self, emotion: Emotion) -> Expression:
        """感情タグを表情に変換"""
        mapping = {
            Emotion.HAPPY: Expression.HAPPY,
            Emotion.SAD: Expression.SAD,
            Emotion.EXCITED: Expression.EXCITED,
            Emotion.SURPRISED: Expression.SURPRISED,
            Emotion.ANGRY: Expression.ANGRY,
            Emotion.NEUTRAL: Expression.NEUTRAL,
        }
        return mapping.get(emotion, Expression.NEUTRAL)

    async def process_script(
        self,
        script: Script,
        progress_callback: Optional[Callable[[int, int, str], None]] = None,
    ) -> Path:
        """台本全体を処理して動画を生成

        Args:
            script: 台本
            progress_callback: 進捗コールバック (current, total, status)

        Returns:
            出力動画のパス
        """
        work_dir = self.config.output_dir / script.title.replace(" ", "_")
        work_dir.mkdir(parents=True, exist_ok=True)

        total = len(script.lines)
        results: list[LineResult] = []

        logger.info(f"Processing script: {script.title} ({total} lines)")

        # 各行を処理
        for i, line in enumerate(script.lines):
            if progress_callback:
                progress_callback(i + 1, total, f"Processing line {i + 1}...")

            result = await self.process_line(line, i, work_dir)
            results.append(result)

        # セグメントを動画に結合
        if progress_callback:
            progress_callback(total, total, "Composing video...")

        output_path = work_dir / f"{script.title.replace(' ', '_')}.mp4"

        segments = [
            {"audio": r.audio_path, "frames_dir": r.frames_dir}
            for r in results
        ]

        success = await self._composer.compose_from_segments(
            segments=segments,
            output_path=output_path,
            background_image=self.config.background_image,
        )

        if not success:
            raise RuntimeError("Failed to compose video")

        logger.info(f"✅ Video created: {output_path}")
        return output_path

    async def close(self):
        """リソースを解放"""
        await self._tts.close()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()


async def quick_record(
    script_path: Path,
    avatar_parts: AvatarParts,
    output_dir: Optional[Path] = None,
    tts_config: Optional[TTSConfig] = None,
) -> Path:
    """簡易収録関数

    Args:
        script_path: 台本ファイルパス
        avatar_parts: アバターパーツ
        output_dir: 出力ディレクトリ（省略時は./output）
        tts_config: TTS設定（省略時はデフォルト）

    Returns:
        出力動画のパス
    """
    script = Script.from_file(script_path)

    config = PipelineConfig(
        tts=tts_config or TTSConfig(),
        lipsync=LipsyncConfig(),
        video=VideoConfig(),
        avatar_parts=avatar_parts,
        output_dir=output_dir or Path("./output"),
    )

    async with RecordingPipeline(config) as pipeline:
        return await pipeline.process_script(script)

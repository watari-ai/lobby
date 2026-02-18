"""Recording Pipeline - 収録ワークフロー統合"""

from dataclasses import dataclass, field
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
from .subtitle import SubtitleFormat, SubtitleGenerator, SubtitleTrack
from .tts import TTSClient, TTSConfig
from .video import VideoComposer, VideoConfig, get_audio_duration_ms


@dataclass
class SubtitleConfig:
    """字幕設定"""
    enabled: bool = True
    burn_in: bool = False  # 動画に焼き込むか
    formats: list[SubtitleFormat] = field(
        default_factory=lambda: [SubtitleFormat.SRT]
    )
    speaker: Optional[str] = None
    font_size: int = 48
    font_name: str = "Noto Sans CJK JP"
    margin_bottom: int = 60
    outline_width: int = 3


@dataclass
class PipelineConfig:
    """パイプライン設定"""
    tts: TTSConfig
    lipsync: LipsyncConfig
    video: VideoConfig
    avatar_parts: AvatarParts
    output_dir: Path = Path("./output")
    background_image: Optional[Path] = None
    subtitle: SubtitleConfig = field(default_factory=SubtitleConfig)

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

        # 字幕を生成
        subtitle_paths: dict[SubtitleFormat, Path] = {}
        if self.config.subtitle.enabled:
            if progress_callback:
                progress_callback(total, total, "Generating subtitles...")

            subtitle_paths = self._generate_subtitles(results, work_dir, script.title)

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

        # 字幕焼き込み
        if self.config.subtitle.burn_in and SubtitleFormat.SRT in subtitle_paths:
            if progress_callback:
                progress_callback(total, total, "Burning in subtitles...")

            burned_path = output_path.with_stem(output_path.stem + "_subtitled")
            burn_success = await self._composer.burn_subtitles(
                video_path=output_path,
                subtitle_path=subtitle_paths[SubtitleFormat.SRT],
                output_path=burned_path,
                font_size=self.config.subtitle.font_size,
                font_name=self.config.subtitle.font_name,
                margin_bottom=self.config.subtitle.margin_bottom,
                outline_width=self.config.subtitle.outline_width,
            )
            if burn_success:
                # 焼き込み版を本体にリネーム
                output_path.unlink()
                burned_path.rename(output_path)
                logger.info("Subtitles burned into video")

        logger.info(f"✅ Video created: {output_path}")
        if subtitle_paths:
            logger.info(f"📝 Subtitles: {list(subtitle_paths.values())}")
        return output_path

    def _generate_subtitles(
        self,
        results: list[LineResult],
        work_dir: Path,
        title: str,
    ) -> dict[SubtitleFormat, Path]:
        """収録結果から字幕ファイルを生成"""
        sub_config = self.config.subtitle
        generator = SubtitleGenerator(speaker=sub_config.speaker)
        track = generator.create_track(title)

        current_time_ms = 0
        gap_ms = 200  # セグメント間のギャップ

        for result in results:
            text = result.line.text.strip()
            duration_ms = result.duration_ms if result.duration_ms > 0 else 2000

            if text:
                track.add_entry(
                    text=text,
                    start_ms=current_time_ms,
                    end_ms=current_time_ms + duration_ms,
                    speaker=sub_config.speaker,
                )

            current_time_ms += duration_ms
            current_time_ms += int(result.line.wait_after * 1000)
            current_time_ms += gap_ms

        # 保存
        output_paths: dict[SubtitleFormat, Path] = {}
        base_name = title.replace(" ", "_")

        for fmt in sub_config.formats:
            out_path = work_dir / f"{base_name}.{fmt.value}"
            track.save(out_path, fmt)
            output_paths[fmt] = out_path

        logger.info(f"Generated subtitles: {list(output_paths.values())}")
        return output_paths

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

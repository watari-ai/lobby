"""Avatar Engine - PNG立ち絵ベースのリップシンク"""

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional

import numpy as np
from loguru import logger

try:
    from PIL import Image
    HAS_PIL = True
except ImportError:
    HAS_PIL = False
    logger.warning("PIL not installed. Image processing disabled.")

try:
    import scipy.io.wavfile as wavfile
    HAS_SCIPY_AUDIO = True
except ImportError:
    HAS_SCIPY_AUDIO = False
    logger.warning("scipy not installed. Audio analysis disabled.")


class MouthShape(Enum):
    """口の形状（基本的なリップシンク用）"""
    CLOSED = "closed"      # 閉じた口（デフォルト）
    OPEN_SMALL = "open_s"  # 少し開いた口
    OPEN_MEDIUM = "open_m" # 中程度に開いた口
    OPEN_LARGE = "open_l"  # 大きく開いた口


class Expression(Enum):
    """表情"""
    NEUTRAL = "neutral"
    HAPPY = "happy"
    SAD = "sad"
    EXCITED = "excited"
    SURPRISED = "surprised"
    ANGRY = "angry"


@dataclass
class AvatarFrame:
    """アバターの1フレーム"""
    timestamp_ms: int           # タイムスタンプ（ミリ秒）
    mouth_shape: MouthShape     # 口の形状
    expression: Expression = Expression.NEUTRAL
    blink: bool = False         # まばたき


@dataclass
class AvatarParts:
    """PNG立ち絵パーツ"""
    base: Path                  # ベース画像（体）
    mouth_closed: Path          # 口閉じ
    mouth_open_s: Path | None = None   # 口開き（小）
    mouth_open_m: Path | None = None   # 口開き（中）
    mouth_open_l: Path | None = None   # 口開き（大）
    eyes_open: Path | None = None      # 目開き
    eyes_closed: Path | None = None    # 目閉じ（まばたき用）

    # 表情差分（オプション）
    expressions: dict[Expression, Path] = field(default_factory=dict)


@dataclass
class LipsyncConfig:
    """リップシンク設定"""
    fps: int = 30                    # フレームレート
    mouth_sensitivity: float = 0.5   # 口の開き感度 (0.0-1.0)
    blink_interval_ms: int = 3000    # まばたき間隔（ミリ秒）
    blink_duration_ms: int = 150     # まばたき時間（ミリ秒）

    # 音量閾値（正規化された値 0.0-1.0）
    threshold_small: float = 0.1     # 小さく開く閾値
    threshold_medium: float = 0.3    # 中程度に開く閾値
    threshold_large: float = 0.6     # 大きく開く閾値


class LipsyncAnalyzer:
    """音声からリップシンクデータを生成"""

    def __init__(self, config: LipsyncConfig | None = None):
        self.config = config or LipsyncConfig()

    def analyze_audio(self, audio_path: Path) -> list[AvatarFrame]:
        """音声ファイルからリップシンクフレームを生成

        Args:
            audio_path: 音声ファイルパス

        Returns:
            AvatarFrameのリスト
        """
        if not HAS_SCIPY_AUDIO:
            logger.warning("scipy not available, returning silent frames")
            return self._generate_silent_frames(1000)  # ダミー

        try:
            # mp3などの場合はffmpegでwavに変換
            import shutil
            import subprocess
            import tempfile

            ffmpeg = shutil.which("ffmpeg")
            if not ffmpeg:
                logger.error("ffmpeg not found")
                return self._generate_silent_frames(1000)

            # 一時wavファイルに変換
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                tmp_path = tmp.name

            cmd = [
                ffmpeg, "-y", "-i", str(audio_path),
                "-ar", "16000",  # 16kHz
                "-ac", "1",      # mono
                "-f", "wav",
                tmp_path,
            ]
            subprocess.run(cmd, capture_output=True, check=True)

            # wavを読み込み
            sample_rate, samples = wavfile.read(tmp_path)

            # 一時ファイル削除
            Path(tmp_path).unlink(missing_ok=True)

        except Exception as e:
            logger.error(f"Failed to load audio: {e}")
            return self._generate_silent_frames(1000)

        # 正規化
        samples = samples.astype(np.float32)
        max_amplitude = np.abs(samples).max()
        if max_amplitude > 0:
            samples = samples / max_amplitude

        duration_ms = int(len(samples) / sample_rate * 1000)
        frame_duration_ms = 1000 // self.config.fps

        frames: list[AvatarFrame] = []

        for frame_idx in range(0, duration_ms, frame_duration_ms):
            # このフレームに対応するサンプル範囲
            start_sample = int(frame_idx * sample_rate / 1000)
            end_sample = int((frame_idx + frame_duration_ms) * sample_rate / 1000)

            if start_sample >= len(samples):
                break

            frame_samples = samples[start_sample:min(end_sample, len(samples))]

            # RMS（音量）を計算
            rms = np.sqrt(np.mean(frame_samples ** 2)) if len(frame_samples) > 0 else 0

            # 感度を適用
            rms = rms * (1 + self.config.mouth_sensitivity)

            # 口の形状を決定
            mouth_shape = self._rms_to_mouth_shape(rms)

            # まばたきチェック
            blink = self._should_blink(frame_idx)

            frames.append(AvatarFrame(
                timestamp_ms=frame_idx,
                mouth_shape=mouth_shape,
                blink=blink,
            ))

        logger.info(f"Generated {len(frames)} lipsync frames for {duration_ms}ms audio")
        return frames

    def _rms_to_mouth_shape(self, rms: float) -> MouthShape:
        """RMS値から口の形状を決定"""
        if rms >= self.config.threshold_large:
            return MouthShape.OPEN_LARGE
        elif rms >= self.config.threshold_medium:
            return MouthShape.OPEN_MEDIUM
        elif rms >= self.config.threshold_small:
            return MouthShape.OPEN_SMALL
        else:
            return MouthShape.CLOSED

    def _should_blink(self, timestamp_ms: int) -> bool:
        """まばたきすべきタイミングか判定"""
        interval = self.config.blink_interval_ms
        duration = self.config.blink_duration_ms

        # 周期的にまばたき
        cycle_position = timestamp_ms % interval
        return cycle_position < duration

    def _generate_silent_frames(self, duration_ms: int) -> list[AvatarFrame]:
        """無音用のフレームを生成"""
        frame_duration_ms = 1000 // self.config.fps
        frames = []

        for frame_idx in range(0, duration_ms, frame_duration_ms):
            frames.append(AvatarFrame(
                timestamp_ms=frame_idx,
                mouth_shape=MouthShape.CLOSED,
                blink=self._should_blink(frame_idx),
            ))

        return frames


class AvatarRenderer:
    """PNG立ち絵のレンダリング"""

    def __init__(self, parts: AvatarParts):
        self.parts = parts
        self._cache: dict[str, Image.Image] = {}

    def _load_image(self, path: Path) -> Optional["Image.Image"]:
        """画像を読み込み（キャッシュ付き）"""
        if not HAS_PIL:
            return None

        key = str(path)
        if key not in self._cache:
            if path.exists():
                self._cache[key] = Image.open(path).convert("RGBA")
            else:
                logger.warning(f"Image not found: {path}")
                return None

        return self._cache[key].copy()

    def render_frame(self, frame: AvatarFrame) -> Optional["Image.Image"]:
        """フレームをレンダリング

        Args:
            frame: アバターフレーム

        Returns:
            合成された画像（PIL Image）
        """
        if not HAS_PIL:
            return None

        # ベース画像を読み込み
        base = self._load_image(self.parts.base)
        if base is None:
            return None

        # 口パーツを選択
        mouth_path = self._get_mouth_path(frame.mouth_shape)
        if mouth_path:
            mouth = self._load_image(mouth_path)
            if mouth:
                base = Image.alpha_composite(base, mouth)

        # 目パーツを選択（まばたき）
        if frame.blink and self.parts.eyes_closed:
            eyes = self._load_image(self.parts.eyes_closed)
            if eyes:
                base = Image.alpha_composite(base, eyes)
        elif self.parts.eyes_open:
            eyes = self._load_image(self.parts.eyes_open)
            if eyes:
                base = Image.alpha_composite(base, eyes)

        # 表情差分を適用
        if frame.expression in self.parts.expressions:
            expr_path = self.parts.expressions[frame.expression]
            expr = self._load_image(expr_path)
            if expr:
                base = Image.alpha_composite(base, expr)

        return base

    def _get_mouth_path(self, shape: MouthShape) -> Optional[Path]:
        """口の形状に対応するパス取得"""
        if shape == MouthShape.CLOSED:
            return self.parts.mouth_closed
        elif shape == MouthShape.OPEN_SMALL:
            return self.parts.mouth_open_s or self.parts.mouth_closed
        elif shape == MouthShape.OPEN_MEDIUM:
            return self.parts.mouth_open_m or self.parts.mouth_open_s or self.parts.mouth_closed
        elif shape == MouthShape.OPEN_LARGE:
            return self.parts.mouth_open_l or self.parts.mouth_open_m or self.parts.mouth_open_s
        return self.parts.mouth_closed

    def render_animation(
        self,
        frames: list[AvatarFrame],
        output_dir: Path,
        prefix: str = "frame",
    ) -> list[Path]:
        """フレームシーケンスをレンダリング

        Args:
            frames: アバターフレームのリスト
            output_dir: 出力ディレクトリ
            prefix: ファイル名プレフィックス

        Returns:
            生成されたフレーム画像のパスリスト
        """
        output_dir.mkdir(parents=True, exist_ok=True)
        paths = []

        for i, frame in enumerate(frames):
            img = self.render_frame(frame)
            if img:
                path = output_dir / f"{prefix}_{i:06d}.png"
                img.save(path)
                paths.append(path)

        logger.info(f"Rendered {len(paths)} frames to {output_dir}")
        return paths

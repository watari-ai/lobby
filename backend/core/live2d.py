"""Live2D Avatar Engine - Live2Dモデル用パラメータ生成"""

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np
from loguru import logger

if TYPE_CHECKING:
    from .emotion import Emotion

try:
    import scipy.io.wavfile as wavfile
    HAS_SCIPY_AUDIO = True
except ImportError:
    HAS_SCIPY_AUDIO = False
    logger.warning("scipy not installed. Audio analysis disabled.")


class Live2DExpression(Enum):
    """Live2D用表情プリセット"""
    NEUTRAL = "neutral"
    HAPPY = "happy"
    SAD = "sad"
    EXCITED = "excited"
    SURPRISED = "surprised"
    ANGRY = "angry"


@dataclass
class Live2DParameters:
    """Live2Dモデルパラメータ

    Cubism標準パラメータ名を使用
    """
    # 口関連 (0.0-1.0)
    param_mouth_open_y: float = 0.0        # 口の開き（縦）
    param_mouth_form: float = 0.0          # 口の形（-1: への字, 1: 笑顔）

    # 目関連 (0.0-1.0)
    param_eye_l_open: float = 1.0          # 左目の開き
    param_eye_r_open: float = 1.0          # 右目の開き
    param_eye_ball_x: float = 0.0          # 目玉X (-1 to 1)
    param_eye_ball_y: float = 0.0          # 目玉Y (-1 to 1)

    # 眉関連 (-1 to 1)
    param_brow_l_y: float = 0.0            # 左眉Y
    param_brow_r_y: float = 0.0            # 右眉Y

    # 顔の向き (-30 to 30 degrees)
    param_angle_x: float = 0.0             # 顔の向き左右
    param_angle_y: float = 0.0             # 顔の向き上下
    param_angle_z: float = 0.0             # 顔の傾き

    # 体の向き (-10 to 10 degrees)
    param_body_angle_x: float = 0.0        # 体の向き左右
    param_body_angle_y: float = 0.0        # 体の向き前後
    param_body_angle_z: float = 0.0        # 体の傾き

    # 呼吸 (0.0-1.0)
    param_breath: float = 0.0

    def to_dict(self) -> dict[str, float]:
        """パラメータを辞書形式で返す"""
        return {
            "ParamMouthOpenY": self.param_mouth_open_y,
            "ParamMouthForm": self.param_mouth_form,
            "ParamEyeLOpen": self.param_eye_l_open,
            "ParamEyeROpen": self.param_eye_r_open,
            "ParamEyeBallX": self.param_eye_ball_x,
            "ParamEyeBallY": self.param_eye_ball_y,
            "ParamBrowLY": self.param_brow_l_y,
            "ParamBrowRY": self.param_brow_r_y,
            "ParamAngleX": self.param_angle_x,
            "ParamAngleY": self.param_angle_y,
            "ParamAngleZ": self.param_angle_z,
            "ParamBodyAngleX": self.param_body_angle_x,
            "ParamBodyAngleY": self.param_body_angle_y,
            "ParamBodyAngleZ": self.param_body_angle_z,
            "ParamBreath": self.param_breath,
        }


@dataclass
class Live2DFrame:
    """Live2Dの1フレーム"""
    timestamp_ms: int
    parameters: Live2DParameters = field(default_factory=Live2DParameters)
    expression: Live2DExpression = Live2DExpression.NEUTRAL
    motion: str | None = None  # 再生するモーション名


@dataclass
class Live2DConfig:
    """Live2D設定"""
    fps: int = 30
    mouth_sensitivity: float = 0.5
    blink_interval_ms: int = 3000
    blink_duration_ms: int = 150
    breath_cycle_ms: int = 4000
    idle_motion_interval_ms: int = 10000

    # 表情ごとのパラメータオフセット
    expression_presets: dict[Live2DExpression, dict[str, float]] = field(
        default_factory=lambda: {
            Live2DExpression.NEUTRAL: {},
            Live2DExpression.HAPPY: {
                "param_mouth_form": 0.5,
                "param_eye_l_open": 0.9,
                "param_eye_r_open": 0.9,
            },
            Live2DExpression.SAD: {
                "param_mouth_form": -0.3,
                "param_brow_l_y": -0.3,
                "param_brow_r_y": -0.3,
                "param_eye_l_open": 0.7,
                "param_eye_r_open": 0.7,
            },
            Live2DExpression.EXCITED: {
                "param_mouth_form": 0.8,
                "param_brow_l_y": 0.3,
                "param_brow_r_y": 0.3,
                "param_eye_l_open": 1.0,
                "param_eye_r_open": 1.0,
            },
            Live2DExpression.SURPRISED: {
                "param_mouth_open_y": 0.4,
                "param_brow_l_y": 0.5,
                "param_brow_r_y": 0.5,
                "param_eye_l_open": 1.0,
                "param_eye_r_open": 1.0,
            },
            Live2DExpression.ANGRY: {
                "param_mouth_form": -0.5,
                "param_brow_l_y": -0.5,
                "param_brow_r_y": -0.5,
            },
        }
    )


class Live2DLipsyncAnalyzer:
    """音声からLive2Dリップシンクパラメータを生成"""

    def __init__(self, config: Live2DConfig | None = None):
        self.config = config or Live2DConfig()

    def analyze_audio(
        self,
        audio_path: Path,
        expression: Live2DExpression = Live2DExpression.NEUTRAL,
    ) -> list[Live2DFrame]:
        """音声ファイルからLive2Dフレームを生成

        Args:
            audio_path: 音声ファイルパス
            expression: 表情プリセット

        Returns:
            Live2DFrameのリスト
        """
        if not HAS_SCIPY_AUDIO:
            logger.warning("scipy not available, returning idle frames")
            return self._generate_idle_frames(1000, expression)

        try:
            # mp3などの場合はffmpegでwavに変換
            import shutil
            import subprocess
            import tempfile

            ffmpeg = shutil.which("ffmpeg")
            if not ffmpeg:
                logger.error("ffmpeg not found")
                return self._generate_idle_frames(1000, expression)

            # 一時wavファイルに変換
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                tmp_path = tmp.name

            cmd = [
                ffmpeg, "-y", "-i", str(audio_path),
                "-ar", "16000",
                "-ac", "1",
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
            return self._generate_idle_frames(1000, expression)

        # 正規化
        samples = samples.astype(np.float32)
        max_amplitude = np.abs(samples).max()
        if max_amplitude > 0:
            samples = samples / max_amplitude

        duration_ms = int(len(samples) / sample_rate * 1000)
        frame_duration_ms = 1000 // self.config.fps

        frames: list[Live2DFrame] = []

        for frame_idx in range(0, duration_ms, frame_duration_ms):
            # このフレームに対応するサンプル範囲
            start_sample = int(frame_idx * sample_rate / 1000)
            end_sample = int((frame_idx + frame_duration_ms) * sample_rate / 1000)

            if start_sample >= len(samples):
                break

            frame_samples = samples[start_sample:min(end_sample, len(samples))]

            # RMS（音量）を計算
            rms = float(np.sqrt(np.mean(frame_samples ** 2))) if len(frame_samples) > 0 else 0.0

            # パラメータを生成
            params = self._generate_parameters(frame_idx, rms, expression)

            frames.append(Live2DFrame(
                timestamp_ms=frame_idx,
                parameters=params,
                expression=expression,
            ))

        logger.info(f"Generated {len(frames)} Live2D frames for {duration_ms}ms audio")
        return frames

    def _generate_parameters(
        self,
        timestamp_ms: int,
        mouth_rms: float,
        expression: Live2DExpression,
    ) -> Live2DParameters:
        """フレームごとのパラメータを生成"""
        params = Live2DParameters()

        # 口の開き（RMSから計算、感度を適用）
        mouth_open = min(1.0, mouth_rms * (1 + self.config.mouth_sensitivity) * 2)
        params.param_mouth_open_y = mouth_open

        # まばたき
        blink_value = self._calculate_blink(timestamp_ms)
        params.param_eye_l_open = 1.0 - blink_value
        params.param_eye_r_open = 1.0 - blink_value

        # 呼吸
        params.param_breath = self._calculate_breath(timestamp_ms)

        # 表情プリセットを適用
        expr_preset = self.config.expression_presets.get(expression, {})
        for key, value in expr_preset.items():
            if hasattr(params, key):
                # プリセット値を加算（口の開きなどは上書きされない）
                if key == "param_mouth_open_y":
                    params.param_mouth_open_y = max(params.param_mouth_open_y, value)
                elif key in ("param_eye_l_open", "param_eye_r_open"):
                    # まばたき中は表情より優先
                    if blink_value < 0.5:
                        setattr(params, key, value)
                else:
                    setattr(params, key, value)

        return params

    def _calculate_blink(self, timestamp_ms: int) -> float:
        """まばたき値を計算 (0.0: 目開き, 1.0: 目閉じ)"""
        interval = self.config.blink_interval_ms
        duration = self.config.blink_duration_ms

        cycle_position = timestamp_ms % interval

        if cycle_position < duration:
            # まばたき中
            progress = cycle_position / duration
            # スムーズな開閉（サイン波）
            return np.sin(progress * np.pi)
        return 0.0

    def _calculate_breath(self, timestamp_ms: int) -> float:
        """呼吸値を計算 (0.0-1.0)"""
        cycle = self.config.breath_cycle_ms
        progress = (timestamp_ms % cycle) / cycle
        # サイン波で自然な呼吸
        return (np.sin(progress * 2 * np.pi - np.pi / 2) + 1) / 2

    def _generate_idle_frames(
        self,
        duration_ms: int,
        expression: Live2DExpression,
    ) -> list[Live2DFrame]:
        """アイドル（無音）用フレームを生成"""
        frame_duration_ms = 1000 // self.config.fps
        frames = []

        for frame_idx in range(0, duration_ms, frame_duration_ms):
            params = self._generate_parameters(frame_idx, 0.0, expression)
            frames.append(Live2DFrame(
                timestamp_ms=frame_idx,
                parameters=params,
                expression=expression,
            ))

        return frames


@dataclass
class Live2DModel:
    """Live2Dモデル情報"""
    model_path: Path              # .model3.json パス
    name: str = ""
    motions: list[str] = field(default_factory=list)       # 利用可能なモーション
    expressions: list[str] = field(default_factory=list)   # 利用可能な表情

    @classmethod
    def from_model_json(cls, model_json_path: Path) -> "Live2DModel":
        """model3.jsonからモデル情報を読み込み"""
        import json

        with open(model_json_path) as f:
            data = json.load(f)

        name = model_json_path.stem.replace(".model3", "")
        motions = []
        expressions = []

        # モーション取得
        if "FileReferences" in data and "Motions" in data["FileReferences"]:
            for group, motion_list in data["FileReferences"]["Motions"].items():
                for i, _ in enumerate(motion_list):
                    motions.append(f"{group}_{i}")

        # 表情取得
        if "FileReferences" in data and "Expressions" in data["FileReferences"]:
            for expr in data["FileReferences"]["Expressions"]:
                expressions.append(expr.get("Name", ""))

        return cls(
            model_path=model_json_path,
            name=name,
            motions=motions,
            expressions=expressions,
        )


def emotion_to_live2d_expression(emotion: "Emotion") -> Live2DExpression:
    """感情タグをLive2D表情に変換

    Args:
        emotion: emotion.pyのEmotion列挙型

    Returns:
        対応するLive2DExpression
    """
    from .emotion import Emotion

    mapping = {
        Emotion.HAPPY: Live2DExpression.HAPPY,
        Emotion.SAD: Live2DExpression.SAD,
        Emotion.EXCITED: Live2DExpression.EXCITED,
        Emotion.ANGRY: Live2DExpression.ANGRY,
        Emotion.SURPRISED: Live2DExpression.SURPRISED,
        Emotion.NEUTRAL: Live2DExpression.NEUTRAL,
    }
    return mapping.get(emotion, Live2DExpression.NEUTRAL)


@dataclass
class EmotionDrivenConfig:
    """感情エンジン統合設定"""
    # 感情強度に応じたパラメータ乗数
    intensity_multiplier: float = 1.5
    # 低強度時に neutral にフォールバックする閾値
    neutral_threshold: float = 0.3
    # 感情遷移のスムージング（フレーム数）
    transition_frames: int = 10


class EmotionDrivenLive2D:
    """感情エンジンとLive2Dの統合クラス

    テキスト入力から感情分析を行い、Live2Dパラメータを生成する
    """

    def __init__(
        self,
        live2d_config: Live2DConfig | None = None,
        emotion_config: EmotionDrivenConfig | None = None,
    ):
        from .emotion import EmotionAnalyzer

        self.live2d_config = live2d_config or Live2DConfig()
        self.emotion_config = emotion_config or EmotionDrivenConfig()
        self.emotion_analyzer = EmotionAnalyzer()
        self.lipsync_analyzer = Live2DLipsyncAnalyzer(self.live2d_config)

        # 現在の感情状態（スムージング用）
        self._current_expression = Live2DExpression.NEUTRAL
        self._current_intensity = 0.5
        self._transition_progress = 1.0

    def analyze_text(self, text: str) -> tuple[Live2DExpression, float]:
        """テキストから感情を分析し、Live2D表情と強度を返す

        Args:
            text: 分析するテキスト

        Returns:
            (Live2DExpression, intensity)
        """
        result = self.emotion_analyzer.analyze(text)
        expression = emotion_to_live2d_expression(result.primary)
        intensity = result.intensity

        # 強度が閾値以下ならneutralにフォールバック
        if intensity < self.emotion_config.neutral_threshold:
            expression = Live2DExpression.NEUTRAL
            intensity = 0.5

        return expression, intensity

    def generate_speaking_frames(
        self,
        text: str,
        audio_path: Path,
    ) -> list[Live2DFrame]:
        """テキストと音声から感情付きLive2Dフレームを生成

        Args:
            text: 台詞テキスト（感情分析用）
            audio_path: 音声ファイルパス（リップシンク用）

        Returns:
            Live2DFrameのリスト
        """
        # テキストから感情を分析
        expression, intensity = self.analyze_text(text)
        logger.info(f"Detected emotion: {expression.value} (intensity: {intensity:.2f})")

        # 音声からリップシンクフレームを生成
        frames = self.lipsync_analyzer.analyze_audio(audio_path, expression)

        # 感情強度に応じてパラメータを調整
        self._apply_intensity(frames, intensity)

        return frames

    def _apply_intensity(
        self,
        frames: list[Live2DFrame],
        intensity: float,
    ) -> None:
        """感情強度をフレームに適用"""
        multiplier = 1.0 + (intensity - 0.5) * self.emotion_config.intensity_multiplier

        for frame in frames:
            params = frame.parameters

            # 表情関連パラメータに強度を適用
            params.param_mouth_form *= multiplier
            params.param_brow_l_y *= multiplier
            params.param_brow_r_y *= multiplier

            # 範囲をクリップ
            params.param_mouth_form = max(-1.0, min(1.0, params.param_mouth_form))
            params.param_brow_l_y = max(-1.0, min(1.0, params.param_brow_l_y))
            params.param_brow_r_y = max(-1.0, min(1.0, params.param_brow_r_y))

    def get_expression_params(
        self,
        text: str,
    ) -> tuple[Live2DExpression, Live2DParameters]:
        """テキストから静的な表情パラメータを取得

        リップシンクなしで表情のみを更新したい場合に使用

        Args:
            text: 分析するテキスト

        Returns:
            (Live2DExpression, Live2DParameters)
        """
        expression, intensity = self.analyze_text(text)

        # 表情プリセットを取得
        preset = self.live2d_config.expression_presets.get(expression, {})
        params = Live2DParameters()

        # プリセットを適用
        for key, value in preset.items():
            if hasattr(params, key):
                setattr(params, key, value)

        # 強度を適用
        multiplier = 1.0 + (intensity - 0.5) * self.emotion_config.intensity_multiplier
        params.param_mouth_form *= multiplier
        params.param_brow_l_y *= multiplier
        params.param_brow_r_y *= multiplier

        return expression, params

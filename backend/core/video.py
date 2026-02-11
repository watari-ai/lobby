"""Video Output - 動画生成エンジン"""

import asyncio
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from loguru import logger


@dataclass
class VideoConfig:
    """動画出力設定"""
    fps: int = 30
    width: int = 1920
    height: int = 1080
    codec: str = "libx264"
    audio_codec: str = "aac"
    crf: int = 23  # 品質（0-51、小さいほど高品質）
    preset: str = "medium"  # エンコード速度 (ultrafast, fast, medium, slow)
    pixel_format: str = "yuv420p"

    # 背景色（透過なしの場合）
    background_color: str = "#00FF00"  # クロマキー用グリーン


class VideoComposer:
    """フレームシーケンスと音声から動画を生成"""

    def __init__(self, config: VideoConfig | None = None):
        self.config = config or VideoConfig()
        self._ffmpeg_path = self._find_ffmpeg()

    def _find_ffmpeg(self) -> Optional[str]:
        """ffmpegのパスを探す"""
        path = shutil.which("ffmpeg")
        if path:
            logger.info(f"Found ffmpeg: {path}")
        else:
            logger.warning("ffmpeg not found in PATH")
        return path

    async def compose(
        self,
        frames_dir: Path,
        audio_path: Path,
        output_path: Path,
        frame_pattern: str = "frame_%06d.png",
        background_image: Optional[Path] = None,
    ) -> bool:
        """フレームシーケンスと音声を合成して動画を生成

        Args:
            frames_dir: フレーム画像が入ったディレクトリ
            audio_path: 音声ファイルパス
            output_path: 出力動画パス
            frame_pattern: フレームファイル名パターン
            background_image: 背景画像（オプション）

        Returns:
            成功したかどうか
        """
        if not self._ffmpeg_path:
            logger.error("ffmpeg not available")
            return False

        output_path.parent.mkdir(parents=True, exist_ok=True)

        # ffmpegコマンドを構築
        cmd = [self._ffmpeg_path, "-y"]  # -y: 上書き許可

        # 入力: フレームシーケンス
        cmd.extend([
            "-framerate", str(self.config.fps),
            "-i", str(frames_dir / frame_pattern),
        ])

        # 入力: 音声
        cmd.extend(["-i", str(audio_path)])

        # 背景画像がある場合はフィルタで合成
        if background_image and background_image.exists():
            cmd.extend([
                "-i", str(background_image),
                "-filter_complex",
                "[2:v][0:v]overlay=(W-w)/2:(H-h)/2[out]",
                "-map", "[out]",
                "-map", "1:a",
            ])
        else:
            cmd.extend(["-map", "0:v", "-map", "1:a"])

        # 出力設定
        cmd.extend([
            "-c:v", self.config.codec,
            "-crf", str(self.config.crf),
            "-preset", self.config.preset,
            "-pix_fmt", self.config.pixel_format,
            "-c:a", self.config.audio_codec,
            "-shortest",  # 短い方に合わせる
            str(output_path),
        ])

        logger.info(f"Running ffmpeg: {' '.join(cmd)}")

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await proc.communicate()

            if proc.returncode != 0:
                logger.error(f"ffmpeg failed: {stderr.decode()}")
                return False

            logger.info(f"Video created: {output_path}")
            return True

        except Exception as e:
            logger.error(f"Failed to run ffmpeg: {e}")
            return False

    async def compose_from_segments(
        self,
        segments: list[dict],
        output_path: Path,
        background_image: Optional[Path] = None,
    ) -> bool:
        """複数セグメント（音声+フレーム）を結合して1本の動画を生成

        Args:
            segments: [{"audio": Path, "frames_dir": Path}, ...]
            output_path: 出力動画パス
            background_image: 背景画像

        Returns:
            成功したかどうか
        """
        if not self._ffmpeg_path:
            logger.error("ffmpeg not available")
            return False

        if not segments:
            logger.error("No segments provided")
            return False

        # 一時ディレクトリを作成
        temp_dir = output_path.parent / ".temp_compose"
        temp_dir.mkdir(parents=True, exist_ok=True)

        try:
            # 各セグメントを個別の動画に変換
            segment_videos = []
            for i, seg in enumerate(segments):
                seg_output = temp_dir / f"segment_{i:04d}.mp4"
                success = await self.compose(
                    frames_dir=seg["frames_dir"],
                    audio_path=seg["audio"],
                    output_path=seg_output,
                    background_image=background_image,
                )
                if success:
                    segment_videos.append(seg_output)
                else:
                    logger.warning(f"Segment {i} failed, skipping")

            if not segment_videos:
                logger.error("No segments were successfully rendered")
                return False

            # concat用のリストファイルを作成
            concat_list = temp_dir / "concat_list.txt"
            with concat_list.open("w") as f:
                for video in segment_videos:
                    f.write(f"file '{video}'\n")

            # セグメントを結合
            cmd = [
                self._ffmpeg_path, "-y",
                "-f", "concat",
                "-safe", "0",
                "-i", str(concat_list),
                "-c", "copy",
                str(output_path),
            ]

            logger.info(f"Concatenating {len(segment_videos)} segments")

            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await proc.communicate()

            if proc.returncode != 0:
                logger.error(f"Concat failed: {stderr.decode()}")
                return False

            logger.info(f"Final video created: {output_path}")
            return True

        finally:
            # 一時ファイルをクリーンアップ
            shutil.rmtree(temp_dir, ignore_errors=True)

    async def add_background(
        self,
        input_video: Path,
        background: Path,
        output_path: Path,
        position: tuple[int, int] = (0, 0),
    ) -> bool:
        """動画に背景を追加（クロマキー合成）

        Args:
            input_video: 入力動画（グリーンバック等）
            background: 背景画像/動画
            output_path: 出力パス
            position: アバターの位置 (x, y)

        Returns:
            成功したかどうか
        """
        if not self._ffmpeg_path:
            return False

        x, y = position

        cmd = [
            self._ffmpeg_path, "-y",
            "-i", str(background),
            "-i", str(input_video),
            "-filter_complex",
            f"[1:v]chromakey={self.config.background_color}:0.1:0.2[fg];"
            f"[0:v][fg]overlay={x}:{y}[out]",
            "-map", "[out]",
            "-map", "1:a?",  # 音声があれば
            "-c:v", self.config.codec,
            "-c:a", self.config.audio_codec,
            str(output_path),
        ]

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            _, stderr = await proc.communicate()

            if proc.returncode != 0:
                logger.error(f"Chromakey failed: {stderr.decode()}")
                return False

            return True

        except Exception as e:
            logger.error(f"Failed: {e}")
            return False


async def get_audio_duration_ms(audio_path: Path) -> int:
    """音声ファイルの長さを取得（ミリ秒）"""
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        logger.warning("ffprobe not found")
        return 0

    cmd = [
        ffprobe, "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(audio_path),
    ]

    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _ = await proc.communicate()

        duration_sec = float(stdout.decode().strip())
        return int(duration_sec * 1000)

    except Exception as e:
        logger.error(f"Failed to get duration: {e}")
        return 0

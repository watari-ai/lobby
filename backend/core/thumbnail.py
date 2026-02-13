"""
Automatic Thumbnail Generation for Lobby.

Generates thumbnails from video recordings:
- Best frame selection from highlights
- Multiple size outputs (YouTube, Twitter, etc.)
- Quality analysis (brightness, contrast, blur)
- Optional text overlay

Requires FFmpeg and Pillow to be installed.
"""

import asyncio
import json
import logging
import shutil
import subprocess
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

import numpy as np

try:
    from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageStat
    HAS_PILLOW = True
except ImportError:
    HAS_PILLOW = False
    Image = None

from .highlight import Highlight

logger = logging.getLogger(__name__)


@dataclass
class ThumbnailSize:
    """Predefined thumbnail sizes for different platforms."""
    name: str
    width: int
    height: int

    @classmethod
    def youtube(cls) -> "ThumbnailSize":
        return cls("youtube", 1280, 720)

    @classmethod
    def twitter(cls) -> "ThumbnailSize":
        return cls("twitter", 1200, 675)

    @classmethod
    def square(cls) -> "ThumbnailSize":
        return cls("square", 1080, 1080)

    @classmethod
    def vertical(cls) -> "ThumbnailSize":
        return cls("vertical", 1080, 1920)

    @classmethod
    def discord(cls) -> "ThumbnailSize":
        return cls("discord", 800, 450)


@dataclass
class ThumbnailConfig:
    """Configuration for thumbnail generation."""
    # Output settings
    default_sizes: list[ThumbnailSize] = field(default_factory=lambda: [
        ThumbnailSize.youtube(),
        ThumbnailSize.twitter(),
        ThumbnailSize.square(),
    ])
    output_format: str = "png"  # png, jpg, webp
    jpeg_quality: int = 95      # For jpg/webp

    # Frame extraction
    frames_per_highlight: int = 5    # Frames to extract per highlight
    frame_interval_ms: int = 200     # Interval between frames

    # Quality thresholds
    min_brightness: float = 0.15     # Reject too dark frames
    max_brightness: float = 0.85     # Reject too bright frames
    min_contrast: float = 0.1        # Reject low contrast frames
    max_blur: float = 100.0          # Reject blurry frames (Laplacian variance)

    # Text overlay
    overlay_enabled: bool = False
    overlay_font_size: int = 72
    overlay_font_color: str = "#FFFFFF"
    overlay_shadow: bool = True
    overlay_position: str = "bottom"  # top, center, bottom


@dataclass
class FrameQuality:
    """Quality metrics for a single frame."""
    brightness: float    # 0.0 to 1.0
    contrast: float      # Standard deviation of luminance
    blur_score: float    # Laplacian variance (higher = sharper)

    @property
    def overall_score(self) -> float:
        """Calculate overall quality score."""
        # Brightness penalty (prefer middle range)
        brightness_score = 1.0 - abs(self.brightness - 0.5) * 2

        # Contrast score (prefer higher)
        contrast_score = min(self.contrast / 0.3, 1.0)

        # Sharpness score (prefer higher, normalize)
        sharpness_score = min(self.blur_score / 200.0, 1.0)

        # Weighted average
        return (brightness_score * 0.3 + contrast_score * 0.3 + sharpness_score * 0.4)


@dataclass
class ThumbnailResult:
    """Result of thumbnail generation."""
    success: bool
    output_paths: list[Path] = field(default_factory=list)
    selected_frame_ms: int = 0
    quality: Optional[FrameQuality] = None
    error: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "success": self.success,
            "output_paths": [str(p) for p in self.output_paths],
            "selected_frame_ms": self.selected_frame_ms,
            "quality": {
                "brightness": self.quality.brightness,
                "contrast": self.quality.contrast,
                "blur_score": self.quality.blur_score,
                "overall_score": self.quality.overall_score,
            } if self.quality else None,
            "error": self.error,
        }


class ThumbnailGenerator:
    """
    Generates thumbnails from video files.

    Uses FFmpeg for frame extraction and Pillow for processing.
    """

    def __init__(self, config: Optional[ThumbnailConfig] = None):
        self.config = config or ThumbnailConfig()
        self._check_dependencies()

    def _check_dependencies(self):
        """Check required dependencies."""
        if not shutil.which("ffmpeg"):
            logger.warning("FFmpeg not found. Thumbnail extraction will fail.")
        if not HAS_PILLOW:
            logger.warning("Pillow not found. Image processing will be limited.")

    def _ms_to_timestamp(self, ms: int) -> str:
        """Convert milliseconds to FFmpeg timestamp format."""
        total_seconds = ms / 1000
        hours = int(total_seconds // 3600)
        minutes = int((total_seconds % 3600) // 60)
        seconds = total_seconds % 60
        return f"{hours:02d}:{minutes:02d}:{seconds:06.3f}"

    def _get_video_duration_ms(self, video_path: Path) -> int:
        """Get video duration in milliseconds using FFprobe."""
        try:
            result = subprocess.run(
                [
                    "ffprobe", "-v", "quiet",
                    "-show_entries", "format=duration",
                    "-of", "json",
                    str(video_path)
                ],
                capture_output=True,
                text=True
            )
            data = json.loads(result.stdout)
            duration_sec = float(data["format"]["duration"])
            return int(duration_sec * 1000)
        except Exception as e:
            logger.error(f"Failed to get video duration: {e}")
            return 0

    async def extract_frame(
        self,
        video_path: Path,
        timestamp_ms: int,
        output_path: Path
    ) -> bool:
        """
        Extract a single frame from video.

        Args:
            video_path: Source video path
            timestamp_ms: Timestamp in milliseconds
            output_path: Output image path

        Returns:
            True if successful
        """
        timestamp = self._ms_to_timestamp(timestamp_ms)

        cmd = [
            "ffmpeg", "-y",
            "-ss", timestamp,
            "-i", str(video_path),
            "-vframes", "1",
            "-q:v", "2",  # High quality
            str(output_path)
        ]

        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            await process.communicate()
            return process.returncode == 0 and output_path.exists()
        except Exception as e:
            logger.error(f"Frame extraction failed: {e}")
            return False

    def analyze_frame_quality(self, image_path: Path) -> Optional[FrameQuality]:
        """
        Analyze image quality metrics.

        Args:
            image_path: Path to image file

        Returns:
            FrameQuality with metrics
        """
        if not HAS_PILLOW:
            logger.warning("Pillow not available, skipping quality analysis")
            return FrameQuality(brightness=0.5, contrast=0.2, blur_score=100.0)

        try:
            with Image.open(image_path) as img:
                # Convert to grayscale for analysis
                gray = img.convert("L")

                # Calculate brightness (mean luminance)
                stat = ImageStat.Stat(gray)
                brightness = stat.mean[0] / 255.0

                # Calculate contrast (standard deviation)
                contrast = stat.stddev[0] / 255.0

                # Calculate blur score using Laplacian variance
                # Higher value = sharper image
                np_gray = np.array(gray, dtype=np.float64)
                np.array([
                    [0, 1, 0],
                    [1, -4, 1],
                    [0, 1, 0]
                ], dtype=np.float64)

                # Simple convolution for blur detection
                from scipy import ndimage
                blur_score = ndimage.laplace(np_gray).var()

                return FrameQuality(
                    brightness=brightness,
                    contrast=contrast,
                    blur_score=blur_score
                )

        except ImportError:
            # scipy not available, use simpler method
            try:
                with Image.open(image_path) as img:
                    gray = img.convert("L")
                    stat = ImageStat.Stat(gray)
                    brightness = stat.mean[0] / 255.0
                    contrast = stat.stddev[0] / 255.0

                    # Estimate blur using edge detection
                    edges = gray.filter(ImageFilter.FIND_EDGES)
                    edge_stat = ImageStat.Stat(edges)
                    blur_score = edge_stat.stddev[0] * 2  # Scale up

                    return FrameQuality(
                        brightness=brightness,
                        contrast=contrast,
                        blur_score=blur_score
                    )
            except Exception as e:
                logger.error(f"Quality analysis failed: {e}")
                return None
        except Exception as e:
            logger.error(f"Quality analysis failed: {e}")
            return None

    def _is_frame_acceptable(self, quality: FrameQuality) -> bool:
        """Check if frame meets quality thresholds."""
        if quality.brightness < self.config.min_brightness:
            return False
        if quality.brightness > self.config.max_brightness:
            return False
        if quality.contrast < self.config.min_contrast:
            return False
        if quality.blur_score < self.config.max_blur * 0.1:  # Too blurry
            return False
        return True

    async def select_best_frame(
        self,
        video_path: Path,
        center_ms: int,
        temp_dir: Path
    ) -> tuple[Optional[Path], int, Optional[FrameQuality]]:
        """
        Extract multiple frames around a timestamp and select the best one.

        Args:
            video_path: Source video path
            center_ms: Center timestamp in milliseconds
            temp_dir: Temporary directory for frames

        Returns:
            (best_frame_path, timestamp_ms, quality)
        """
        video_duration = self._get_video_duration_ms(video_path)

        # Calculate frame timestamps
        half_count = self.config.frames_per_highlight // 2
        timestamps = []
        for i in range(-half_count, half_count + 1):
            ts = center_ms + (i * self.config.frame_interval_ms)
            if 0 <= ts < video_duration:
                timestamps.append(ts)

        if not timestamps:
            timestamps = [min(max(center_ms, 0), video_duration - 100)]

        # Extract frames
        frame_data: list[tuple[Path, int, FrameQuality]] = []

        for i, ts in enumerate(timestamps):
            frame_path = temp_dir / f"frame_{ts}ms.png"
            success = await self.extract_frame(video_path, ts, frame_path)

            if success and frame_path.exists():
                quality = self.analyze_frame_quality(frame_path)
                if quality and self._is_frame_acceptable(quality):
                    frame_data.append((frame_path, ts, quality))

        if not frame_data:
            # Fall back to any extracted frame
            for ts in timestamps:
                frame_path = temp_dir / f"frame_{ts}ms.png"
                if frame_path.exists():
                    quality = self.analyze_frame_quality(frame_path)
                    if quality:
                        frame_data.append((frame_path, ts, quality))
                        break

        if not frame_data:
            return None, center_ms, None

        # Select best frame by quality score
        best = max(frame_data, key=lambda x: x[2].overall_score)
        return best

    def resize_and_save(
        self,
        source_path: Path,
        output_path: Path,
        size: ThumbnailSize,
        text_overlay: Optional[str] = None
    ) -> bool:
        """
        Resize image and optionally add text overlay.

        Args:
            source_path: Source image path
            output_path: Output path
            size: Target size
            text_overlay: Optional text to overlay

        Returns:
            True if successful
        """
        if not HAS_PILLOW:
            # Fall back to FFmpeg for resize
            return self._resize_with_ffmpeg(source_path, output_path, size)

        try:
            with Image.open(source_path) as img:
                # Calculate crop to maintain aspect ratio
                target_ratio = size.width / size.height
                img_ratio = img.width / img.height

                if img_ratio > target_ratio:
                    # Image is wider, crop sides
                    new_width = int(img.height * target_ratio)
                    left = (img.width - new_width) // 2
                    img = img.crop((left, 0, left + new_width, img.height))
                else:
                    # Image is taller, crop top/bottom
                    new_height = int(img.width / target_ratio)
                    top = (img.height - new_height) // 2
                    img = img.crop((0, top, img.width, top + new_height))

                # Resize
                img = img.resize((size.width, size.height), Image.Resampling.LANCZOS)

                # Add text overlay if requested
                if text_overlay and self.config.overlay_enabled:
                    img = self._add_text_overlay(img, text_overlay)

                # Save
                output_path.parent.mkdir(parents=True, exist_ok=True)

                if self.config.output_format.lower() in ("jpg", "jpeg"):
                    img = img.convert("RGB")
                    img.save(output_path, "JPEG", quality=self.config.jpeg_quality)
                elif self.config.output_format.lower() == "webp":
                    img.save(output_path, "WEBP", quality=self.config.jpeg_quality)
                else:
                    img.save(output_path, "PNG")

                return True

        except Exception as e:
            logger.error(f"Resize failed: {e}")
            return False

    def _resize_with_ffmpeg(
        self,
        source_path: Path,
        output_path: Path,
        size: ThumbnailSize
    ) -> bool:
        """Fallback resize using FFmpeg."""
        output_path.parent.mkdir(parents=True, exist_ok=True)

        cmd = [
            "ffmpeg", "-y",
            "-i", str(source_path),
            "-vf", f"scale={size.width}:{size.height}:force_original_aspect_ratio=increase,crop={size.width}:{size.height}",
            str(output_path)
        ]

        try:
            result = subprocess.run(cmd, capture_output=True)
            return result.returncode == 0
        except Exception as e:
            logger.error(f"FFmpeg resize failed: {e}")
            return False

    def _add_text_overlay(self, img: Image.Image, text: str) -> Image.Image:
        """Add text overlay to image."""
        draw = ImageDraw.Draw(img)

        # Try to use a nice font, fall back to default
        try:
            font = ImageFont.truetype("/System/Library/Fonts/ヒラギノ角ゴシック W6.ttc",
                                      self.config.overlay_font_size)
        except Exception:
            try:
                font = ImageFont.truetype("Arial.ttf", self.config.overlay_font_size)
            except Exception:
                font = ImageFont.load_default()

        # Calculate text position
        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]

        x = (img.width - text_width) // 2

        if self.config.overlay_position == "top":
            y = 40
        elif self.config.overlay_position == "center":
            y = (img.height - text_height) // 2
        else:  # bottom
            y = img.height - text_height - 60

        # Draw shadow
        if self.config.overlay_shadow:
            shadow_offset = max(2, self.config.overlay_font_size // 20)
            draw.text((x + shadow_offset, y + shadow_offset), text,
                     font=font, fill="#000000")

        # Draw text
        draw.text((x, y), text, font=font, fill=self.config.overlay_font_color)

        return img

    async def generate_from_highlight(
        self,
        video_path: Path,
        highlight: Highlight,
        output_dir: Optional[Path] = None,
        sizes: Optional[list[ThumbnailSize]] = None,
        text_overlay: Optional[str] = None
    ) -> ThumbnailResult:
        """
        Generate thumbnails from a highlight moment.

        Args:
            video_path: Source video path
            highlight: Highlight to use as source
            output_dir: Output directory
            sizes: Thumbnail sizes to generate
            text_overlay: Optional text overlay

        Returns:
            ThumbnailResult
        """
        video_path = Path(video_path)
        if not video_path.exists():
            return ThumbnailResult(success=False, error=f"Video not found: {video_path}")

        output_dir = output_dir or (video_path.parent / "thumbnails")
        sizes = sizes or self.config.default_sizes

        # Create temp directory
        temp_dir = output_dir / ".temp_frames"
        temp_dir.mkdir(parents=True, exist_ok=True)

        try:
            # Select best frame around highlight
            center_ms = highlight.timestamp_ms + (highlight.duration_ms // 2)
            best_frame, selected_ms, quality = await self.select_best_frame(
                video_path, center_ms, temp_dir
            )

            if best_frame is None:
                return ThumbnailResult(
                    success=False,
                    error="Failed to extract any acceptable frames"
                )

            # Generate thumbnails for each size
            output_paths = []
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

            for size in sizes:
                ext = self.config.output_format
                filename = f"thumbnail_{size.name}_{timestamp}.{ext}"
                output_path = output_dir / filename

                if self.resize_and_save(best_frame, output_path, size, text_overlay):
                    output_paths.append(output_path)
                    logger.info(f"Generated thumbnail: {output_path}")

            if not output_paths:
                return ThumbnailResult(
                    success=False,
                    error="Failed to generate any thumbnails"
                )

            return ThumbnailResult(
                success=True,
                output_paths=output_paths,
                selected_frame_ms=selected_ms,
                quality=quality
            )

        finally:
            # Cleanup temp files
            shutil.rmtree(temp_dir, ignore_errors=True)

    async def generate_from_video(
        self,
        video_path: Path,
        highlights: Optional[list[Highlight]] = None,
        output_dir: Optional[Path] = None,
        sizes: Optional[list[ThumbnailSize]] = None,
        text_overlay: Optional[str] = None
    ) -> ThumbnailResult:
        """
        Generate thumbnails from video, optionally using highlights.

        If no highlights provided, samples frames evenly across video.

        Args:
            video_path: Source video path
            highlights: Optional highlights to prefer
            output_dir: Output directory
            sizes: Thumbnail sizes
            text_overlay: Optional text overlay

        Returns:
            ThumbnailResult
        """
        video_path = Path(video_path)
        if not video_path.exists():
            return ThumbnailResult(success=False, error=f"Video not found: {video_path}")

        output_dir = output_dir or (video_path.parent / "thumbnails")
        sizes = sizes or self.config.default_sizes
        temp_dir = output_dir / ".temp_frames"
        temp_dir.mkdir(parents=True, exist_ok=True)

        try:
            duration_ms = self._get_video_duration_ms(video_path)
            if duration_ms == 0:
                return ThumbnailResult(success=False, error="Could not get video duration")

            # Determine candidate timestamps
            if highlights:
                # Sort by score and take top 5
                sorted_highlights = sorted(highlights, key=lambda h: h.score, reverse=True)[:5]
                candidates = [(h.timestamp_ms + h.duration_ms // 2) for h in sorted_highlights]
            else:
                # Sample evenly across video (skip first/last 10%)
                start = int(duration_ms * 0.1)
                end = int(duration_ms * 0.9)
                step = (end - start) // 10
                candidates = list(range(start, end, step))[:10]

            # Find best frame among all candidates
            all_frames: list[tuple[Path, int, FrameQuality]] = []

            for timestamp in candidates:
                frame_path = temp_dir / f"candidate_{timestamp}.png"
                if await self.extract_frame(video_path, timestamp, frame_path):
                    quality = self.analyze_frame_quality(frame_path)
                    if quality and self._is_frame_acceptable(quality):
                        all_frames.append((frame_path, timestamp, quality))

            if not all_frames:
                # Fall back to middle of video
                mid = duration_ms // 2
                frame_path = temp_dir / "fallback.png"
                if await self.extract_frame(video_path, mid, frame_path):
                    quality = self.analyze_frame_quality(frame_path)
                    if quality:
                        all_frames.append((frame_path, mid, quality))

            if not all_frames:
                return ThumbnailResult(
                    success=False,
                    error="Could not extract any frames from video"
                )

            # Select best frame
            best_frame, selected_ms, quality = max(
                all_frames, key=lambda x: x[2].overall_score
            )

            # Generate thumbnails
            output_paths = []
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

            for size in sizes:
                ext = self.config.output_format
                filename = f"thumbnail_{size.name}_{timestamp}.{ext}"
                output_path = output_dir / filename

                if self.resize_and_save(best_frame, output_path, size, text_overlay):
                    output_paths.append(output_path)
                    logger.info(f"Generated thumbnail: {output_path}")

            if not output_paths:
                return ThumbnailResult(
                    success=False,
                    error="Failed to generate thumbnails"
                )

            return ThumbnailResult(
                success=True,
                output_paths=output_paths,
                selected_frame_ms=selected_ms,
                quality=quality
            )

        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    async def generate_at_timestamp(
        self,
        video_path: Path,
        timestamp_ms: int,
        output_dir: Optional[Path] = None,
        sizes: Optional[list[ThumbnailSize]] = None,
        text_overlay: Optional[str] = None
    ) -> ThumbnailResult:
        """
        Generate thumbnail at a specific timestamp.

        Args:
            video_path: Source video path
            timestamp_ms: Timestamp in milliseconds
            output_dir: Output directory
            sizes: Thumbnail sizes
            text_overlay: Optional text overlay

        Returns:
            ThumbnailResult
        """
        video_path = Path(video_path)
        if not video_path.exists():
            return ThumbnailResult(success=False, error=f"Video not found: {video_path}")

        output_dir = output_dir or (video_path.parent / "thumbnails")
        sizes = sizes or self.config.default_sizes
        temp_dir = output_dir / ".temp_frames"
        temp_dir.mkdir(parents=True, exist_ok=True)

        try:
            # Extract and select best frame
            best_frame, selected_ms, quality = await self.select_best_frame(
                video_path, timestamp_ms, temp_dir
            )

            if best_frame is None:
                return ThumbnailResult(
                    success=False,
                    error=f"Failed to extract frame at {timestamp_ms}ms"
                )

            # Generate thumbnails
            output_paths = []
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

            for size in sizes:
                ext = self.config.output_format
                filename = f"thumbnail_{size.name}_{timestamp}.{ext}"
                output_path = output_dir / filename

                if self.resize_and_save(best_frame, output_path, size, text_overlay):
                    output_paths.append(output_path)

            return ThumbnailResult(
                success=True,
                output_paths=output_paths,
                selected_frame_ms=selected_ms,
                quality=quality
            )

        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)


class ThumbnailManager:
    """
    High-level interface for thumbnail generation.

    Combines highlight detection with thumbnail generation.
    """

    def __init__(
        self,
        generator: Optional[ThumbnailGenerator] = None
    ):
        self.generator = generator or ThumbnailGenerator()

    async def auto_generate(
        self,
        video_path: Path,
        session_log_path: Optional[Path] = None,
        output_dir: Optional[Path] = None,
        sizes: Optional[list[ThumbnailSize]] = None,
        text_overlay: Optional[str] = None
    ) -> ThumbnailResult:
        """
        Automatically detect highlights and generate best thumbnail.

        Args:
            video_path: Source video path
            session_log_path: Optional session log for highlight detection
            output_dir: Output directory
            sizes: Thumbnail sizes
            text_overlay: Optional text overlay

        Returns:
            ThumbnailResult
        """
        from .highlight import HighlightDetector

        video_path = Path(video_path)

        # Detect highlights
        detector = HighlightDetector()
        all_highlights = []

        # Analyze audio for highlights
        try:
            audio_highlights = await detector.analyze_audio_file(video_path)
            all_highlights.extend(audio_highlights)
        except Exception as e:
            logger.warning(f"Audio analysis failed: {e}")

        # Analyze session log if provided
        if session_log_path and Path(session_log_path).exists():
            try:
                log_highlights = await detector.analyze_session_log(Path(session_log_path))
                all_highlights.extend(log_highlights)
            except Exception as e:
                logger.warning(f"Session log analysis failed: {e}")

        # Generate thumbnail
        return await self.generator.generate_from_video(
            video_path=video_path,
            highlights=all_highlights if all_highlights else None,
            output_dir=output_dir,
            sizes=sizes,
            text_overlay=text_overlay
        )

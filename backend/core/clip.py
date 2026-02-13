"""
Clip Extraction for Lobby.

Extracts video clips based on highlights:
- Single clip extraction (from highlight)
- Highlight reel generation (multiple clips concatenated)
- Custom time range extraction
- Various output formats (MP4, WebM, GIF)

Requires FFmpeg to be installed.
"""

import asyncio
import json
import logging
import shutil
import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

from .highlight import Highlight, HighlightDetector

logger = logging.getLogger(__name__)


@dataclass
class ClipConfig:
    """Configuration for clip extraction."""
    # Time padding
    pre_buffer_ms: int = 2000      # Time before highlight
    post_buffer_ms: int = 3000     # Time after highlight

    # Output settings
    default_format: str = "mp4"    # mp4, webm, gif
    video_codec: str = "libx264"   # For MP4
    audio_codec: str = "aac"       # For MP4
    crf: int = 23                  # Quality (lower = better, 18-28 typical)
    preset: str = "medium"         # Encoding speed (ultrafast to veryslow)

    # GIF settings
    gif_fps: int = 15
    gif_width: int = 480

    # Highlight reel
    transition_ms: int = 500       # Fade between clips
    max_clips: int = 10            # Maximum clips in reel

    # Metadata
    add_timestamp_overlay: bool = False
    add_type_label: bool = False


@dataclass
class ClipResult:
    """Result of a clip extraction."""
    success: bool
    output_path: Optional[Path] = None
    duration_ms: int = 0
    error: Optional[str] = None
    highlight: Optional[Highlight] = None

    def to_dict(self) -> dict:
        return {
            "success": self.success,
            "output_path": str(self.output_path) if self.output_path else None,
            "duration_ms": self.duration_ms,
            "error": self.error,
            "highlight": self.highlight.to_dict() if self.highlight else None
        }


class ClipExtractor:
    """
    Extracts video clips based on highlights.

    Uses FFmpeg for video processing.
    """

    def __init__(self, config: Optional[ClipConfig] = None):
        self.config = config or ClipConfig()
        self._check_ffmpeg()

    def _check_ffmpeg(self):
        """Verify FFmpeg is installed."""
        if not shutil.which("ffmpeg"):
            logger.warning("FFmpeg not found. Clip extraction will fail.")

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

    async def extract_clip(
        self,
        video_path: Path,
        start_ms: int,
        end_ms: int,
        output_path: Optional[Path] = None,
        format: Optional[str] = None,
        highlight: Optional[Highlight] = None
    ) -> ClipResult:
        """
        Extract a single clip from video.

        Args:
            video_path: Source video path
            start_ms: Start time in milliseconds
            end_ms: End time in milliseconds
            output_path: Output path (auto-generated if None)
            format: Output format (mp4, webm, gif)
            highlight: Associated highlight (for metadata)

        Returns:
            ClipResult with extraction status
        """
        video_path = Path(video_path)
        if not video_path.exists():
            return ClipResult(success=False, error=f"Video not found: {video_path}")

        # Get video duration to clamp values
        video_duration = self._get_video_duration_ms(video_path)
        if video_duration == 0:
            return ClipResult(success=False, error="Could not determine video duration")

        # Clamp start/end times
        start_ms = max(0, start_ms)
        end_ms = min(video_duration, end_ms)

        if start_ms >= end_ms:
            return ClipResult(success=False, error=f"Invalid time range: {start_ms}ms to {end_ms}ms")

        duration_ms = end_ms - start_ms
        format = format or self.config.default_format

        # Generate output path
        if output_path is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            clip_name = f"clip_{timestamp}_{start_ms}_{end_ms}"
            output_path = video_path.parent / "clips" / f"{clip_name}.{format}"

        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Build FFmpeg command
        start_ts = self._ms_to_timestamp(start_ms)
        duration_ts = self._ms_to_timestamp(duration_ms)

        if format == "gif":
            cmd = await self._build_gif_command(video_path, output_path, start_ts, duration_ts)
        else:
            cmd = self._build_video_command(video_path, output_path, start_ts, duration_ts, format)

        logger.info(f"Extracting clip: {start_ms}ms to {end_ms}ms -> {output_path}")
        logger.debug(f"FFmpeg command: {' '.join(cmd)}")

        # Run FFmpeg
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await process.communicate()

            if process.returncode != 0:
                error_msg = stderr.decode()[-500:]  # Last 500 chars
                logger.error(f"FFmpeg failed: {error_msg}")
                return ClipResult(success=False, error=f"FFmpeg error: {error_msg}")

            logger.info(f"Clip extracted successfully: {output_path}")
            return ClipResult(
                success=True,
                output_path=output_path,
                duration_ms=duration_ms,
                highlight=highlight
            )

        except Exception as e:
            logger.error(f"Clip extraction failed: {e}")
            return ClipResult(success=False, error=str(e))

    def _build_video_command(
        self,
        input_path: Path,
        output_path: Path,
        start_ts: str,
        duration_ts: str,
        format: str
    ) -> list[str]:
        """Build FFmpeg command for video output."""
        cmd = [
            "ffmpeg", "-y",
            "-ss", start_ts,
            "-i", str(input_path),
            "-t", duration_ts,
        ]

        if format == "mp4":
            cmd.extend([
                "-c:v", self.config.video_codec,
                "-c:a", self.config.audio_codec,
                "-crf", str(self.config.crf),
                "-preset", self.config.preset,
                "-movflags", "+faststart"
            ])
        elif format == "webm":
            cmd.extend([
                "-c:v", "libvpx-vp9",
                "-c:a", "libopus",
                "-crf", str(self.config.crf),
                "-b:v", "0"
            ])

        cmd.append(str(output_path))
        return cmd

    async def _build_gif_command(
        self,
        input_path: Path,
        output_path: Path,
        start_ts: str,
        duration_ts: str
    ) -> list[str]:
        """Build FFmpeg command for GIF output."""
        # GIF requires a palette for good quality
        return [
            "ffmpeg", "-y",
            "-ss", start_ts,
            "-i", str(input_path),
            "-t", duration_ts,
            "-vf", f"fps={self.config.gif_fps},scale={self.config.gif_width}:-1:flags=lanczos,split[s0][s1];[s0]palettegen[p];[s1][p]paletteuse",
            str(output_path)
        ]

    async def extract_from_highlight(
        self,
        video_path: Path,
        highlight: Highlight,
        output_dir: Optional[Path] = None,
        format: Optional[str] = None
    ) -> ClipResult:
        """
        Extract a clip from a highlight with pre/post buffer.

        Args:
            video_path: Source video path
            highlight: Highlight to extract
            output_dir: Output directory (default: video_path/clips)
            format: Output format

        Returns:
            ClipResult with extraction status
        """
        start_ms = highlight.timestamp_ms - self.config.pre_buffer_ms
        end_ms = highlight.timestamp_ms + highlight.duration_ms + self.config.post_buffer_ms

        format = format or self.config.default_format

        # Generate descriptive filename
        type_label = highlight.highlight_type.value.replace("_", "-")
        timestamp_sec = highlight.timestamp_ms // 1000
        safe_label = "".join(c if c.isalnum() else "_" for c in highlight.label[:20])
        filename = f"clip_{type_label}_{timestamp_sec}s_{safe_label}.{format}"

        output_dir = output_dir or (Path(video_path).parent / "clips")
        output_path = output_dir / filename

        return await self.extract_clip(
            video_path=video_path,
            start_ms=start_ms,
            end_ms=end_ms,
            output_path=output_path,
            format=format,
            highlight=highlight
        )

    async def extract_all_highlights(
        self,
        video_path: Path,
        highlights: list[Highlight],
        output_dir: Optional[Path] = None,
        format: Optional[str] = None,
        max_clips: Optional[int] = None
    ) -> list[ClipResult]:
        """
        Extract clips from multiple highlights.

        Args:
            video_path: Source video path
            highlights: List of highlights to extract
            output_dir: Output directory
            format: Output format
            max_clips: Maximum number of clips to extract

        Returns:
            List of ClipResults
        """
        max_clips = max_clips or self.config.max_clips
        highlights = sorted(highlights, key=lambda h: h.score, reverse=True)[:max_clips]

        results = []
        for highlight in highlights:
            result = await self.extract_from_highlight(
                video_path=video_path,
                highlight=highlight,
                output_dir=output_dir,
                format=format
            )
            results.append(result)

            # Small delay to avoid overwhelming FFmpeg
            await asyncio.sleep(0.1)

        successful = sum(1 for r in results if r.success)
        logger.info(f"Extracted {successful}/{len(results)} clips from highlights")
        return results

    async def create_highlight_reel(
        self,
        video_path: Path,
        highlights: list[Highlight],
        output_path: Optional[Path] = None,
        max_clips: Optional[int] = None,
        add_transitions: bool = True
    ) -> ClipResult:
        """
        Create a highlight reel by concatenating multiple clips.

        Args:
            video_path: Source video path
            highlights: List of highlights to include
            output_path: Output path for the reel
            max_clips: Maximum clips to include
            add_transitions: Add fade transitions between clips

        Returns:
            ClipResult with the highlight reel
        """
        video_path = Path(video_path)
        max_clips = max_clips or self.config.max_clips

        # Sort by score and take top clips
        top_highlights = sorted(highlights, key=lambda h: h.score, reverse=True)[:max_clips]
        # Re-sort by timestamp for chronological order
        top_highlights = sorted(top_highlights, key=lambda h: h.timestamp_ms)

        if not top_highlights:
            return ClipResult(success=False, error="No highlights to include in reel")

        # Create temp directory for clips
        temp_dir = video_path.parent / ".temp_clips"
        temp_dir.mkdir(exist_ok=True)

        try:
            # Extract individual clips
            clip_files = []
            for i, highlight in enumerate(top_highlights):
                temp_output = temp_dir / f"clip_{i:03d}.mp4"
                result = await self.extract_clip(
                    video_path=video_path,
                    start_ms=highlight.timestamp_ms - self.config.pre_buffer_ms,
                    end_ms=highlight.timestamp_ms + highlight.duration_ms + self.config.post_buffer_ms,
                    output_path=temp_output,
                    format="mp4"
                )
                if result.success:
                    clip_files.append(temp_output)

            if not clip_files:
                return ClipResult(success=False, error="Failed to extract any clips")

            # Generate output path
            if output_path is None:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                output_path = video_path.parent / "clips" / f"highlight_reel_{timestamp}.mp4"

            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)

            # Concatenate clips
            if add_transitions and len(clip_files) > 1:
                result = await self._concat_with_transitions(clip_files, output_path)
            else:
                result = await self._concat_simple(clip_files, output_path)

            if result.success:
                # Calculate total duration
                total_duration = sum(
                    h.duration_ms + self.config.pre_buffer_ms + self.config.post_buffer_ms
                    for h in top_highlights
                )
                result.duration_ms = total_duration

            return result

        finally:
            # Cleanup temp files
            shutil.rmtree(temp_dir, ignore_errors=True)

    async def _concat_simple(self, clip_files: list[Path], output_path: Path) -> ClipResult:
        """Concatenate clips without transitions."""
        # Create concat file
        concat_file = clip_files[0].parent / "concat.txt"
        with open(concat_file, "w") as f:
            for clip in clip_files:
                f.write(f"file '{clip}'\n")

        cmd = [
            "ffmpeg", "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", str(concat_file),
            "-c", "copy",
            str(output_path)
        ]

        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await process.communicate()

            if process.returncode != 0:
                return ClipResult(success=False, error=f"Concat failed: {stderr.decode()[-200:]}")

            logger.info(f"Highlight reel created: {output_path}")
            return ClipResult(success=True, output_path=output_path)

        except Exception as e:
            return ClipResult(success=False, error=str(e))

    async def _concat_with_transitions(self, clip_files: list[Path], output_path: Path) -> ClipResult:
        """Concatenate clips with fade transitions."""
        # Build complex filter for xfade transitions
        fade_duration = self.config.transition_ms / 1000

        # Build input arguments
        inputs = []
        for clip in clip_files:
            inputs.extend(["-i", str(clip)])

        # Build xfade filter chain
        if len(clip_files) == 2:
            # Simple case: two clips
            filter_complex = f"[0:v][1:v]xfade=transition=fade:duration={fade_duration}[v];[0:a][1:a]acrossfade=d={fade_duration}[a]"
            cmd = ["ffmpeg", "-y"] + inputs + [
                "-filter_complex", filter_complex,
                "-map", "[v]", "-map", "[a]",
                "-c:v", self.config.video_codec,
                "-c:a", self.config.audio_codec,
                str(output_path)
            ]
        else:
            # Multiple clips: chain xfade filters
            # This is complex, so fall back to simple concat with short fades
            # For now, use simple concat
            return await self._concat_simple(clip_files, output_path)

        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await process.communicate()

            if process.returncode != 0:
                # Fall back to simple concat
                logger.warning("Transition concat failed, falling back to simple concat")
                return await self._concat_simple(clip_files, output_path)

            logger.info(f"Highlight reel with transitions created: {output_path}")
            return ClipResult(success=True, output_path=output_path)

        except Exception as e:
            return ClipResult(success=False, error=str(e))


class ClipManager:
    """
    High-level interface for clip extraction.

    Combines highlight detection with clip extraction.
    """

    def __init__(
        self,
        detector: Optional[HighlightDetector] = None,
        extractor: Optional[ClipExtractor] = None
    ):
        self.detector = detector or HighlightDetector()
        self.extractor = extractor or ClipExtractor()

    async def auto_clip_video(
        self,
        video_path: Path,
        output_dir: Optional[Path] = None,
        session_log_path: Optional[Path] = None,
        max_clips: int = 5,
        create_reel: bool = True
    ) -> dict:
        """
        Automatically detect highlights and extract clips.

        Args:
            video_path: Source video path
            output_dir: Output directory for clips
            session_log_path: Optional session log for additional highlight data
            max_clips: Maximum clips to extract
            create_reel: Also create a highlight reel

        Returns:
            Dict with clips and reel paths
        """
        video_path = Path(video_path)

        # Detect highlights
        all_highlights = []

        # Analyze audio
        audio_highlights = await self.detector.analyze_audio_file(video_path)
        all_highlights.extend(audio_highlights)

        # Analyze session log if provided
        if session_log_path and Path(session_log_path).exists():
            log_highlights = await self.detector.analyze_session_log(Path(session_log_path))
            all_highlights.extend(log_highlights)

        if not all_highlights:
            logger.warning("No highlights detected")
            return {"clips": [], "reel": None, "highlights_count": 0}

        # Get top highlights
        self.detector.highlights = all_highlights
        top_highlights = self.detector.get_top_highlights(max_clips)

        # Extract clips
        clip_results = await self.extractor.extract_all_highlights(
            video_path=video_path,
            highlights=top_highlights,
            output_dir=output_dir
        )

        result = {
            "clips": [r.to_dict() for r in clip_results if r.success],
            "reel": None,
            "highlights_count": len(all_highlights)
        }

        # Create highlight reel
        if create_reel and len([r for r in clip_results if r.success]) >= 2:
            reel_result = await self.extractor.create_highlight_reel(
                video_path=video_path,
                highlights=top_highlights,
                output_path=output_dir / "highlight_reel.mp4" if output_dir else None
            )
            if reel_result.success:
                result["reel"] = str(reel_result.output_path)

        return result

    async def extract_time_range(
        self,
        video_path: Path,
        start_ms: int,
        end_ms: int,
        output_path: Optional[Path] = None,
        format: str = "mp4"
    ) -> ClipResult:
        """
        Extract a custom time range clip.

        Args:
            video_path: Source video path
            start_ms: Start time in milliseconds
            end_ms: End time in milliseconds
            output_path: Output path
            format: Output format

        Returns:
            ClipResult
        """
        return await self.extractor.extract_clip(
            video_path=Path(video_path),
            start_ms=start_ms,
            end_ms=end_ms,
            output_path=output_path,
            format=format
        )

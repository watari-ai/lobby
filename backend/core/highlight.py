"""
Automatic Highlight Detection for Lobby.

Analyzes recordings and live sessions to identify "highlight moments":
- Audio energy spikes (loud moments, reactions)
- Emotion intensity peaks
- Chat activity spikes (live mode)
- Custom markers from scripts

Used for:
- Auto-generating highlight reels
- Clip extraction suggestions
- Thumbnail selection
"""

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Callable, Optional

import numpy as np

logger = logging.getLogger(__name__)


class HighlightType(str, Enum):
    """Types of highlight events."""
    AUDIO_SPIKE = "audio_spike"        # Loud moment, reaction
    EMOTION_PEAK = "emotion_peak"      # High emotion intensity
    CHAT_BURST = "chat_burst"          # Many chat messages at once
    MANUAL_MARKER = "manual_marker"    # User-added marker
    SUPERCHAT = "superchat"           # Donation/superchat received
    KEYWORD = "keyword"               # Specific keyword detected
    EXPRESSION_CHANGE = "expression"  # Avatar expression change


@dataclass
class Highlight:
    """A single highlight moment."""
    timestamp_ms: int
    duration_ms: int
    highlight_type: HighlightType
    score: float  # 0.0 to 1.0, importance
    label: str
    metadata: dict = field(default_factory=dict)

    @property
    def timestamp_str(self) -> str:
        """Format timestamp as HH:MM:SS.mmm."""
        total_seconds = self.timestamp_ms / 1000
        hours = int(total_seconds // 3600)
        minutes = int((total_seconds % 3600) // 60)
        seconds = total_seconds % 60
        return f"{hours:02d}:{minutes:02d}:{seconds:06.3f}"

    def to_dict(self) -> dict:
        return {
            "timestamp_ms": self.timestamp_ms,
            "timestamp_str": self.timestamp_str,
            "duration_ms": self.duration_ms,
            "type": self.highlight_type.value,
            "score": self.score,
            "label": self.label,
            "metadata": self.metadata
        }


@dataclass
class HighlightConfig:
    """Configuration for highlight detection."""
    # Audio analysis
    audio_threshold: float = 0.7          # RMS threshold for spike (0-1)
    audio_window_ms: int = 500            # Window for audio analysis
    audio_min_duration_ms: int = 1000     # Minimum highlight duration

    # Emotion analysis
    emotion_threshold: float = 0.7        # Emotion intensity threshold
    emotion_types: list[str] = field(default_factory=lambda: [
        "excited", "surprised", "happy", "angry"
    ])

    # Chat analysis (live mode)
    chat_burst_threshold: int = 5         # Messages within window
    chat_burst_window_ms: int = 5000      # Time window for burst detection

    # Merging nearby highlights
    merge_window_ms: int = 3000           # Merge highlights within this window

    # Keyword detection
    highlight_keywords: list[str] = field(default_factory=lambda: [
        "やばい", "すごい", "マジ", "草", "www", "神", "かわいい",
        "amazing", "wow", "omg", "lol", "poggers", "clutch"
    ])

    # Scoring weights
    weights: dict = field(default_factory=lambda: {
        HighlightType.AUDIO_SPIKE.value: 1.0,
        HighlightType.EMOTION_PEAK.value: 0.9,
        HighlightType.CHAT_BURST.value: 0.8,
        HighlightType.SUPERCHAT.value: 1.0,
        HighlightType.KEYWORD.value: 0.6,
        HighlightType.MANUAL_MARKER.value: 1.0,
        HighlightType.EXPRESSION_CHANGE.value: 0.5
    })


class HighlightDetector:
    """
    Detects highlights from various sources.

    Can operate in two modes:
    - Post-recording analysis: Analyze audio/video files
    - Real-time detection: Process events as they happen (live mode)
    """

    def __init__(self, config: Optional[HighlightConfig] = None):
        self.config = config or HighlightConfig()
        self.highlights: list[Highlight] = []
        self._chat_buffer: list[tuple[int, dict]] = []  # (timestamp_ms, chat_data)
        self._is_recording = False
        self._start_time: Optional[datetime] = None

    def start_session(self):
        """Start a new recording/live session."""
        self.highlights = []
        self._chat_buffer = []
        self._is_recording = True
        self._start_time = datetime.now()
        logger.info("Highlight detection session started")

    def stop_session(self) -> list[Highlight]:
        """Stop session and return detected highlights."""
        self._is_recording = False
        merged = self._merge_highlights()
        sorted_highlights = sorted(merged, key=lambda h: h.timestamp_ms)
        logger.info(f"Highlight detection session ended. {len(sorted_highlights)} highlights detected.")
        return sorted_highlights

    def _get_current_timestamp_ms(self) -> int:
        """Get milliseconds since session start."""
        if not self._start_time:
            return 0
        delta = datetime.now() - self._start_time
        return int(delta.total_seconds() * 1000)

    # === Real-time Event Processing ===

    def process_audio_chunk(self, audio_data: np.ndarray, sample_rate: int, timestamp_ms: Optional[int] = None):
        """
        Process an audio chunk for spike detection.

        Args:
            audio_data: Audio samples as numpy array (normalized to -1.0 to 1.0)
            sample_rate: Sample rate in Hz
            timestamp_ms: Override timestamp (for post-processing)
        """
        if timestamp_ms is None:
            timestamp_ms = self._get_current_timestamp_ms()

        # Calculate RMS energy
        rms = np.sqrt(np.mean(audio_data ** 2))

        # Check if above threshold
        if rms >= self.config.audio_threshold:
            duration_ms = len(audio_data) / sample_rate * 1000

            # Check if meets minimum duration
            if duration_ms >= self.config.audio_min_duration_ms:
                highlight = Highlight(
                    timestamp_ms=timestamp_ms,
                    duration_ms=int(duration_ms),
                    highlight_type=HighlightType.AUDIO_SPIKE,
                    score=min(1.0, rms / self.config.audio_threshold),
                    label="Loud moment",
                    metadata={"rms": float(rms)}
                )
                self.highlights.append(highlight)
                logger.debug(f"Audio spike detected at {highlight.timestamp_str} (RMS: {rms:.3f})")

    def process_emotion(self, emotion: str, intensity: float, timestamp_ms: Optional[int] = None):
        """
        Process emotion data for highlight detection.

        Args:
            emotion: Emotion type (e.g., "excited", "happy")
            intensity: Emotion intensity (0.0 to 1.0)
            timestamp_ms: Override timestamp
        """
        if timestamp_ms is None:
            timestamp_ms = self._get_current_timestamp_ms()

        if emotion in self.config.emotion_types and intensity >= self.config.emotion_threshold:
            highlight = Highlight(
                timestamp_ms=timestamp_ms,
                duration_ms=1000,  # Default 1 second
                highlight_type=HighlightType.EMOTION_PEAK,
                score=intensity,
                label=f"{emotion.capitalize()} moment",
                metadata={"emotion": emotion, "intensity": intensity}
            )
            self.highlights.append(highlight)
            logger.debug(f"Emotion peak detected at {highlight.timestamp_str}: {emotion} ({intensity:.2f})")

    def process_chat_message(self, message: dict, timestamp_ms: Optional[int] = None):
        """
        Process a chat message for burst detection and keyword analysis.

        Args:
            message: Chat message dict with keys: author, text, (optional: amount for superchat)
            timestamp_ms: Override timestamp
        """
        if timestamp_ms is None:
            timestamp_ms = self._get_current_timestamp_ms()

        # Add to buffer
        self._chat_buffer.append((timestamp_ms, message))

        # Clean old messages from buffer
        cutoff = timestamp_ms - self.config.chat_burst_window_ms
        self._chat_buffer = [(ts, msg) for ts, msg in self._chat_buffer if ts >= cutoff]

        # Check for superchat
        if message.get("amount"):
            highlight = Highlight(
                timestamp_ms=timestamp_ms,
                duration_ms=2000,
                highlight_type=HighlightType.SUPERCHAT,
                score=min(1.0, message["amount"] / 1000),  # Normalize by amount
                label=f"Superchat from {message.get('author', 'Anonymous')}",
                metadata={"amount": message["amount"], "author": message.get("author")}
            )
            self.highlights.append(highlight)
            logger.debug(f"Superchat received at {highlight.timestamp_str}")

        # Check for keyword
        text = message.get("text", "").lower()
        for keyword in self.config.highlight_keywords:
            if keyword.lower() in text:
                highlight = Highlight(
                    timestamp_ms=timestamp_ms,
                    duration_ms=1000,
                    highlight_type=HighlightType.KEYWORD,
                    score=0.6,
                    label=f"Keyword: {keyword}",
                    metadata={"keyword": keyword, "text": message.get("text")}
                )
                self.highlights.append(highlight)
                break  # Only one keyword highlight per message

        # Check for burst
        if len(self._chat_buffer) >= self.config.chat_burst_threshold:
            # Only create burst highlight if we haven't recently
            recent_bursts = [
                h for h in self.highlights
                if h.highlight_type == HighlightType.CHAT_BURST
                and timestamp_ms - h.timestamp_ms < self.config.chat_burst_window_ms
            ]
            if not recent_bursts:
                highlight = Highlight(
                    timestamp_ms=timestamp_ms,
                    duration_ms=self.config.chat_burst_window_ms,
                    highlight_type=HighlightType.CHAT_BURST,
                    score=min(1.0, len(self._chat_buffer) / (self.config.chat_burst_threshold * 2)),
                    label=f"Chat burst ({len(self._chat_buffer)} messages)",
                    metadata={"message_count": len(self._chat_buffer)}
                )
                self.highlights.append(highlight)
                logger.debug(f"Chat burst detected at {highlight.timestamp_str}")

    def add_manual_marker(self, label: str, timestamp_ms: Optional[int] = None):
        """Add a manual highlight marker."""
        if timestamp_ms is None:
            timestamp_ms = self._get_current_timestamp_ms()

        highlight = Highlight(
            timestamp_ms=timestamp_ms,
            duration_ms=3000,  # Default 3 seconds around marker
            highlight_type=HighlightType.MANUAL_MARKER,
            score=1.0,
            label=label,
            metadata={}
        )
        self.highlights.append(highlight)
        logger.info(f"Manual marker added at {highlight.timestamp_str}: {label}")

    def process_expression_change(self, old_expression: str, new_expression: str, timestamp_ms: Optional[int] = None):
        """Track avatar expression changes as potential highlights."""
        if timestamp_ms is None:
            timestamp_ms = self._get_current_timestamp_ms()

        # Only highlight "interesting" expression changes
        interesting_expressions = {"surprised", "angry", "excited", "crying", "shocked"}
        if new_expression.lower() in interesting_expressions:
            highlight = Highlight(
                timestamp_ms=timestamp_ms,
                duration_ms=2000,
                highlight_type=HighlightType.EXPRESSION_CHANGE,
                score=0.5,
                label=f"Expression: {new_expression}",
                metadata={"from": old_expression, "to": new_expression}
            )
            self.highlights.append(highlight)

    # === Post-Recording Analysis ===

    async def analyze_audio_file(self, audio_path: Path) -> list[Highlight]:
        """
        Analyze an audio file for highlights.

        Args:
            audio_path: Path to audio file (WAV, MP3, etc.)

        Returns:
            List of detected highlights
        """
        try:
            import soundfile as sf
        except ImportError:
            logger.warning("soundfile not installed. Install with: pip install soundfile")
            return []

        logger.info(f"Analyzing audio file: {audio_path}")

        # Load audio
        audio_data, sample_rate = sf.read(audio_path)
        if len(audio_data.shape) > 1:
            audio_data = audio_data.mean(axis=1)  # Convert stereo to mono

        # Normalize
        audio_data = audio_data / (np.max(np.abs(audio_data)) + 1e-10)

        # Process in chunks
        window_samples = int(self.config.audio_window_ms * sample_rate / 1000)
        highlights = []

        for i in range(0, len(audio_data), window_samples):
            chunk = audio_data[i:i + window_samples]
            if len(chunk) < window_samples // 2:
                continue

            timestamp_ms = int(i / sample_rate * 1000)

            # Calculate RMS
            rms = np.sqrt(np.mean(chunk ** 2))

            if rms >= self.config.audio_threshold:
                highlight = Highlight(
                    timestamp_ms=timestamp_ms,
                    duration_ms=self.config.audio_window_ms,
                    highlight_type=HighlightType.AUDIO_SPIKE,
                    score=min(1.0, rms / self.config.audio_threshold),
                    label="Loud moment",
                    metadata={"rms": float(rms)}
                )
                highlights.append(highlight)

        logger.info(f"Found {len(highlights)} audio highlights")
        return highlights

    async def analyze_session_log(self, log_path: Path) -> list[Highlight]:
        """
        Analyze a session log file for highlights.

        Session logs contain emotion data, chat messages, etc.

        Args:
            log_path: Path to JSON session log

        Returns:
            List of detected highlights
        """
        logger.info(f"Analyzing session log: {log_path}")

        with open(log_path, "r", encoding="utf-8") as f:
            log_data = json.load(f)

        highlights = []

        for event in log_data.get("events", []):
            timestamp_ms = event.get("timestamp_ms", 0)
            event_type = event.get("type")

            if event_type == "emotion":
                emotion = event.get("emotion")
                intensity = event.get("intensity", 0)
                if emotion in self.config.emotion_types and intensity >= self.config.emotion_threshold:
                    highlights.append(Highlight(
                        timestamp_ms=timestamp_ms,
                        duration_ms=1000,
                        highlight_type=HighlightType.EMOTION_PEAK,
                        score=intensity,
                        label=f"{emotion.capitalize()} moment",
                        metadata=event
                    ))

            elif event_type == "chat":
                text = event.get("text", "").lower()
                for keyword in self.config.highlight_keywords:
                    if keyword.lower() in text:
                        highlights.append(Highlight(
                            timestamp_ms=timestamp_ms,
                            duration_ms=1000,
                            highlight_type=HighlightType.KEYWORD,
                            score=0.6,
                            label=f"Keyword: {keyword}",
                            metadata=event
                        ))
                        break

                if event.get("amount"):
                    highlights.append(Highlight(
                        timestamp_ms=timestamp_ms,
                        duration_ms=2000,
                        highlight_type=HighlightType.SUPERCHAT,
                        score=min(1.0, event["amount"] / 1000),
                        label="Superchat",
                        metadata=event
                    ))

            elif event_type == "marker":
                highlights.append(Highlight(
                    timestamp_ms=timestamp_ms,
                    duration_ms=3000,
                    highlight_type=HighlightType.MANUAL_MARKER,
                    score=1.0,
                    label=event.get("label", "Marker"),
                    metadata=event
                ))

        logger.info(f"Found {len(highlights)} highlights from session log")
        return highlights

    # === Highlight Processing ===

    def _merge_highlights(self) -> list[Highlight]:
        """Merge nearby highlights of the same type."""
        if not self.highlights:
            return []

        # Sort by timestamp
        sorted_highlights = sorted(self.highlights, key=lambda h: h.timestamp_ms)
        merged = []
        current = sorted_highlights[0]

        for next_highlight in sorted_highlights[1:]:
            # Check if should merge
            gap = next_highlight.timestamp_ms - (current.timestamp_ms + current.duration_ms)
            same_type = current.highlight_type == next_highlight.highlight_type

            if same_type and gap <= self.config.merge_window_ms:
                # Merge: extend duration and take max score
                new_duration = (next_highlight.timestamp_ms + next_highlight.duration_ms) - current.timestamp_ms
                current = Highlight(
                    timestamp_ms=current.timestamp_ms,
                    duration_ms=new_duration,
                    highlight_type=current.highlight_type,
                    score=max(current.score, next_highlight.score),
                    label=current.label,
                    metadata={**current.metadata, **next_highlight.metadata}
                )
            else:
                merged.append(current)
                current = next_highlight

        merged.append(current)
        return merged

    def get_top_highlights(self, n: int = 10) -> list[Highlight]:
        """
        Get top N highlights by weighted score.

        Args:
            n: Number of highlights to return

        Returns:
            Top highlights sorted by weighted score
        """
        def weighted_score(h: Highlight) -> float:
            weight = self.config.weights.get(h.highlight_type.value, 0.5)
            return h.score * weight

        merged = self._merge_highlights()
        sorted_by_score = sorted(merged, key=weighted_score, reverse=True)
        return sorted_by_score[:n]

    def export_highlights(self, output_path: Path):
        """Export highlights to JSON file."""
        merged = self._merge_highlights()
        sorted_highlights = sorted(merged, key=lambda h: h.timestamp_ms)

        data = {
            "generated_at": datetime.now().isoformat(),
            "total_highlights": len(sorted_highlights),
            "highlights": [h.to_dict() for h in sorted_highlights]
        }

        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        logger.info(f"Exported {len(sorted_highlights)} highlights to {output_path}")

    def generate_chapters(self, video_duration_ms: int, max_chapters: int = 10) -> list[dict]:
        """
        Generate YouTube-style chapters from highlights.

        Args:
            video_duration_ms: Total video duration in milliseconds
            max_chapters: Maximum number of chapters

        Returns:
            List of chapter dicts with timestamp and title
        """
        top_highlights = self.get_top_highlights(max_chapters)

        chapters = [{"timestamp_ms": 0, "title": "Start"}]

        for h in sorted(top_highlights, key=lambda x: x.timestamp_ms):
            # Ensure minimum gap between chapters (30 seconds)
            if chapters and h.timestamp_ms - chapters[-1]["timestamp_ms"] < 30000:
                continue
            chapters.append({
                "timestamp_ms": h.timestamp_ms,
                "title": h.label
            })

        return chapters


# === Integration with Recording Mode ===

class HighlightEnabledRecorder:
    """
    Wrapper that adds highlight detection to recording sessions.

    Usage:
        recorder = HighlightEnabledRecorder(detector)
        recorder.start()

        # During recording:
        recorder.on_audio(audio_data, sample_rate)
        recorder.on_emotion(emotion, intensity)
        recorder.on_chat(message)

        # After recording:
        highlights = recorder.stop()
    """

    def __init__(self, detector: Optional[HighlightDetector] = None):
        self.detector = detector or HighlightDetector()
        self._callbacks: list[Callable[[Highlight], None]] = []

    def start(self):
        """Start recording with highlight detection."""
        self.detector.start_session()

    def stop(self) -> list[Highlight]:
        """Stop recording and return highlights."""
        return self.detector.stop_session()

    def on_highlight(self, callback: Callable[[Highlight], None]):
        """Register callback for real-time highlight notifications."""
        self._callbacks.append(callback)

    def on_audio(self, audio_data: np.ndarray, sample_rate: int):
        """Process audio chunk."""
        before = len(self.detector.highlights)
        self.detector.process_audio_chunk(audio_data, sample_rate)
        self._notify_new_highlights(before)

    def on_emotion(self, emotion: str, intensity: float):
        """Process emotion event."""
        before = len(self.detector.highlights)
        self.detector.process_emotion(emotion, intensity)
        self._notify_new_highlights(before)

    def on_chat(self, message: dict):
        """Process chat message."""
        before = len(self.detector.highlights)
        self.detector.process_chat_message(message)
        self._notify_new_highlights(before)

    def add_marker(self, label: str):
        """Add manual marker."""
        before = len(self.detector.highlights)
        self.detector.add_manual_marker(label)
        self._notify_new_highlights(before)

    def _notify_new_highlights(self, before_count: int):
        """Notify callbacks of new highlights."""
        new_highlights = self.detector.highlights[before_count:]
        for highlight in new_highlights:
            for callback in self._callbacks:
                try:
                    callback(highlight)
                except Exception as e:
                    logger.error(f"Highlight callback error: {e}")

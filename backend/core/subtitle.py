"""Subtitle Generator - SRT/VTT字幕生成"""

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional

from loguru import logger


class SubtitleFormat(str, Enum):
    """字幕フォーマット"""
    SRT = "srt"
    VTT = "vtt"


@dataclass
class SubtitleEntry:
    """字幕エントリー"""
    index: int
    start_ms: int
    end_ms: int
    text: str
    speaker: Optional[str] = None  # 話者名（VTT用）
    style: Optional[str] = None  # スタイル指定

    @property
    def start_srt(self) -> str:
        """SRT形式のタイムスタンプ（開始）"""
        return self._ms_to_srt(self.start_ms)

    @property
    def end_srt(self) -> str:
        """SRT形式のタイムスタンプ（終了）"""
        return self._ms_to_srt(self.end_ms)

    @property
    def start_vtt(self) -> str:
        """VTT形式のタイムスタンプ（開始）"""
        return self._ms_to_vtt(self.start_ms)

    @property
    def end_vtt(self) -> str:
        """VTT形式のタイムスタンプ（終了）"""
        return self._ms_to_vtt(self.end_ms)

    @staticmethod
    def _ms_to_srt(ms: int) -> str:
        """ミリ秒をSRT形式に変換 (HH:MM:SS,mmm)"""
        hours = ms // 3600000
        ms %= 3600000
        minutes = ms // 60000
        ms %= 60000
        seconds = ms // 1000
        milliseconds = ms % 1000
        return f"{hours:02d}:{minutes:02d}:{seconds:02d},{milliseconds:03d}"

    @staticmethod
    def _ms_to_vtt(ms: int) -> str:
        """ミリ秒をVTT形式に変換 (HH:MM:SS.mmm)"""
        hours = ms // 3600000
        ms %= 3600000
        minutes = ms // 60000
        ms %= 60000
        seconds = ms // 1000
        milliseconds = ms % 1000
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}.{milliseconds:03d}"

    def to_srt(self) -> str:
        """SRT形式の文字列を生成"""
        return f"{self.index}\n{self.start_srt} --> {self.end_srt}\n{self.text}\n"

    def to_vtt(self) -> str:
        """VTT形式の文字列を生成"""
        cue = f"{self.start_vtt} --> {self.end_vtt}"

        # スタイル指定がある場合
        if self.style:
            cue += f" {self.style}"

        # 話者名がある場合
        text = self.text
        if self.speaker:
            text = f"<v {self.speaker}>{text}"

        return f"{cue}\n{text}\n"


@dataclass
class SubtitleTrack:
    """字幕トラック"""
    entries: list[SubtitleEntry] = field(default_factory=list)
    title: Optional[str] = None
    language: str = "ja"

    def add_entry(
        self,
        text: str,
        start_ms: int,
        end_ms: int,
        speaker: Optional[str] = None,
        style: Optional[str] = None,
    ) -> SubtitleEntry:
        """字幕エントリーを追加"""
        entry = SubtitleEntry(
            index=len(self.entries) + 1,
            start_ms=start_ms,
            end_ms=end_ms,
            text=text,
            speaker=speaker,
            style=style,
        )
        self.entries.append(entry)
        return entry

    def to_srt(self) -> str:
        """SRT形式で出力"""
        lines = []
        for entry in self.entries:
            lines.append(entry.to_srt())
        return "\n".join(lines)

    def to_vtt(self) -> str:
        """VTT形式で出力"""
        lines = ["WEBVTT"]

        # タイトルがあれば追加
        if self.title:
            lines.append(f"Title: {self.title}")

        # 言語指定
        lines.append(f"Language: {self.language}")
        lines.append("")  # 空行

        for entry in self.entries:
            lines.append(entry.to_vtt())

        return "\n".join(lines)

    def save(
        self,
        output_path: Path,
        format: SubtitleFormat = SubtitleFormat.SRT,
    ) -> Path:
        """ファイルに保存"""
        # 拡張子を確認・修正
        if output_path.suffix.lower() not in [".srt", ".vtt"]:
            output_path = output_path.with_suffix(f".{format.value}")

        output_path.parent.mkdir(parents=True, exist_ok=True)

        if format == SubtitleFormat.SRT:
            content = self.to_srt()
        else:
            content = self.to_vtt()

        output_path.write_text(content, encoding="utf-8")
        logger.info(f"Subtitle saved: {output_path}")

        return output_path


class SubtitleGenerator:
    """字幕生成器"""

    def __init__(
        self,
        default_format: SubtitleFormat = SubtitleFormat.SRT,
        language: str = "ja",
        speaker: Optional[str] = None,
    ):
        self.default_format = default_format
        self.language = language
        self.speaker = speaker

    def create_track(self, title: Optional[str] = None) -> SubtitleTrack:
        """新しい字幕トラックを作成"""
        return SubtitleTrack(
            title=title,
            language=self.language,
        )

    def generate_from_segments(
        self,
        segments: list[dict],
        title: Optional[str] = None,
        gap_ms: int = 100,  # セグメント間のギャップ
    ) -> SubtitleTrack:
        """セグメントリストから字幕を生成

        Args:
            segments: [{"text": str, "duration_ms": int}, ...]
            title: トラックタイトル
            gap_ms: セグメント間のギャップ（ミリ秒）

        Returns:
            SubtitleTrack
        """
        track = self.create_track(title)
        current_time = 0

        for seg in segments:
            text = seg.get("text", "")
            duration_ms = seg.get("duration_ms", 2000)

            if not text.strip():
                current_time += duration_ms + gap_ms
                continue

            # 長いテキストは複数行に分割
            lines = self._split_text(text)
            line_duration = duration_ms // len(lines) if lines else duration_ms

            for line in lines:
                track.add_entry(
                    text=line,
                    start_ms=current_time,
                    end_ms=current_time + line_duration,
                    speaker=self.speaker,
                )
                current_time += line_duration

            current_time += gap_ms

        return track

    def _split_text(
        self,
        text: str,
        max_chars: int = 40,
    ) -> list[str]:
        """長いテキストを適切な長さに分割

        Args:
            text: 分割するテキスト
            max_chars: 1行の最大文字数

        Returns:
            分割されたテキストのリスト
        """
        if len(text) <= max_chars:
            return [text]

        lines = []
        current_line = ""

        # 句読点で分割を優先
        split_points = ["。", "！", "？", "、", "…", " "]

        i = 0
        while i < len(text):
            char = text[i]
            current_line += char

            # 最大文字数に近づいたら分割を検討
            if len(current_line) >= max_chars - 5:
                # 分割点を探す
                split_found = False
                for point in split_points:
                    if point in current_line:
                        last_idx = current_line.rfind(point)
                        if last_idx > len(current_line) // 2:
                            lines.append(current_line[:last_idx + 1].strip())
                            current_line = current_line[last_idx + 1:].strip()
                            split_found = True
                            break

                # 分割点がなければ強制分割
                if not split_found and len(current_line) >= max_chars:
                    lines.append(current_line.strip())
                    current_line = ""

            i += 1

        if current_line.strip():
            lines.append(current_line.strip())

        return lines if lines else [text]


async def generate_subtitles_from_recording(
    results: list,
    output_dir: Path,
    title: str = "Recording",
    speaker: Optional[str] = None,
    formats: list[SubtitleFormat] | None = None,
) -> dict[SubtitleFormat, Path]:
    """収録結果から字幕ファイルを生成

    Args:
        results: RecordingResult のリスト
        output_dir: 出力ディレクトリ
        title: 字幕タイトル
        speaker: 話者名
        formats: 出力フォーマット（デフォルト: SRT + VTT両方）

    Returns:
        {format: output_path} の辞書
    """
    from .video import get_audio_duration_ms

    if formats is None:
        formats = [SubtitleFormat.SRT, SubtitleFormat.VTT]

    generator = SubtitleGenerator(speaker=speaker)
    track = generator.create_track(title)

    current_time = 0
    gap_ms = 200  # 行間のギャップ

    for result in results:
        # 音声の正確な長さを取得
        if result.audio_path.exists():
            duration_ms = await get_audio_duration_ms(result.audio_path)
        else:
            duration_ms = result.duration_ms

        if duration_ms <= 0:
            duration_ms = 2000  # フォールバック

        text = result.line.text
        if text.strip():
            track.add_entry(
                text=text,
                start_ms=current_time,
                end_ms=current_time + duration_ms,
                speaker=speaker,
            )

        current_time += duration_ms
        current_time += int(result.line.wait_after * 1000)  # wait_afterを考慮
        current_time += gap_ms

    # 各フォーマットで保存
    output_paths = {}
    base_name = title.replace(" ", "_")

    for fmt in formats:
        output_path = output_dir / f"{base_name}.{fmt.value}"
        track.save(output_path, fmt)
        output_paths[fmt] = output_path

    logger.info(f"Generated subtitles: {list(output_paths.values())}")
    return output_paths

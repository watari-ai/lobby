"""Live Subtitle Manager - リアルタイム字幕管理

ライブモードでの字幕表示と配信を管理する。
"""

import asyncio
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Callable, Optional

from loguru import logger


class SubtitleStyle(str, Enum):
    """字幕スタイル"""
    NORMAL = "normal"  # 通常
    EXCITED = "excited"  # 興奮（大きめ、明るい色）
    SAD = "sad"  # 悲しい（薄め）
    ANGRY = "angry"  # 怒り（赤系）
    WHISPER = "whisper"  # ささやき（小さめ、薄め）
    SHOUT = "shout"  # 叫び（大きめ、太字）


@dataclass
class LiveSubtitle:
    """ライブ字幕エントリー"""
    id: str  # 一意のID
    text: str
    speaker: str = ""
    style: SubtitleStyle = SubtitleStyle.NORMAL
    emotion: str = "neutral"  # 感情タグ
    timestamp: datetime = field(default_factory=datetime.now)
    duration_ms: int = 3000  # 表示時間（ミリ秒）
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        """辞書に変換（WebSocket送信用）"""
        return {
            "id": self.id,
            "text": self.text,
            "speaker": self.speaker,
            "style": self.style.value,
            "emotion": self.emotion,
            "timestamp": self.timestamp.isoformat(),
            "duration_ms": self.duration_ms,
            "metadata": self.metadata,
        }


@dataclass
class SubtitleConfig:
    """字幕設定"""
    # 表示設定
    default_duration_ms: int = 3000  # デフォルト表示時間
    max_chars_per_line: int = 40  # 1行の最大文字数
    max_lines: int = 2  # 最大行数
    fade_in_ms: int = 100  # フェードイン時間
    fade_out_ms: int = 200  # フェードアウト時間

    # スタイルマッピング（感情 → スタイル）
    emotion_style_map: dict = field(default_factory=lambda: {
        "happy": SubtitleStyle.NORMAL,
        "excited": SubtitleStyle.EXCITED,
        "sad": SubtitleStyle.SAD,
        "angry": SubtitleStyle.ANGRY,
        "fear": SubtitleStyle.WHISPER,
        "surprise": SubtitleStyle.EXCITED,
        "neutral": SubtitleStyle.NORMAL,
    })

    # 文字レート（1文字あたりのミリ秒）
    ms_per_char: int = 80  # 日本語基準

    def get_style(self, emotion: str) -> SubtitleStyle:
        """感情からスタイルを取得"""
        return self.emotion_style_map.get(emotion.lower(), SubtitleStyle.NORMAL)

    def calculate_duration(self, text: str) -> int:
        """テキスト長から表示時間を計算"""
        base_duration = len(text) * self.ms_per_char
        # 最低1.5秒、最大10秒
        return max(1500, min(10000, base_duration))


class LiveSubtitleManager:
    """リアルタイム字幕マネージャー

    字幕の生成、キュー管理、ブロードキャストを担当。
    """

    def __init__(self, config: Optional[SubtitleConfig] = None):
        self.config = config or SubtitleConfig()

        # 字幕履歴（アーカイブ用）
        self._history: deque[LiveSubtitle] = deque(maxlen=1000)

        # 現在表示中の字幕
        self._current_subtitle: Optional[LiveSubtitle] = None

        # 字幕カウンター（ID生成用）
        self._counter: int = 0

        # ブロードキャストコールバック
        self._on_subtitle: Optional[Callable[[LiveSubtitle], None]] = None
        self._on_clear: Optional[Callable[[], None]] = None

        # 自動クリアタスク
        self._clear_task: Optional[asyncio.Task] = None

    def set_subtitle_callback(self, callback: Callable[[LiveSubtitle], None]):
        """字幕表示コールバックを設定"""
        self._on_subtitle = callback

    def set_clear_callback(self, callback: Callable[[], None]):
        """字幕クリアコールバックを設定"""
        self._on_clear = callback

    def _generate_id(self) -> str:
        """ユニークIDを生成"""
        self._counter += 1
        timestamp = datetime.now().strftime("%H%M%S%f")
        return f"sub_{timestamp}_{self._counter}"

    def _split_text(self, text: str) -> list[str]:
        """長いテキストを複数行に分割"""
        max_chars = self.config.max_chars_per_line
        if len(text) <= max_chars:
            return [text]

        lines = []
        current_line = ""

        # 句読点で分割を優先
        split_points = ["。", "！", "？", "、", "…", "　", " "]

        for char in text:
            current_line += char

            if len(current_line) >= max_chars - 3:
                # 分割点を探す
                split_found = False
                for point in split_points:
                    if point in current_line[-10:]:
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

        if current_line.strip():
            lines.append(current_line.strip())

        # 最大行数に制限
        return lines[:self.config.max_lines]

    async def show_subtitle(
        self,
        text: str,
        speaker: str = "",
        emotion: str = "neutral",
        duration_ms: Optional[int] = None,
        metadata: Optional[dict] = None,
    ) -> LiveSubtitle:
        """字幕を表示

        Args:
            text: 表示テキスト
            speaker: 話者名
            emotion: 感情（スタイル決定に使用）
            duration_ms: 表示時間（Noneの場合は自動計算）
            metadata: 追加メタデータ

        Returns:
            生成された字幕オブジェクト
        """
        # 前の自動クリアをキャンセル
        if self._clear_task and not self._clear_task.done():
            self._clear_task.cancel()

        # 表示時間を決定
        if duration_ms is None:
            duration_ms = self.config.calculate_duration(text)

        # スタイルを決定
        style = self.config.get_style(emotion)

        # 長いテキストは分割
        lines = self._split_text(text)
        display_text = "\n".join(lines)

        # 字幕オブジェクト作成
        subtitle = LiveSubtitle(
            id=self._generate_id(),
            text=display_text,
            speaker=speaker,
            style=style,
            emotion=emotion,
            duration_ms=duration_ms,
            metadata=metadata or {},
        )

        self._current_subtitle = subtitle
        self._history.append(subtitle)

        logger.debug(f"Subtitle: [{style.value}] {display_text[:30]}...")

        # コールバック呼び出し
        if self._on_subtitle:
            self._on_subtitle(subtitle)

        # 自動クリアをスケジュール
        self._clear_task = asyncio.create_task(
            self._auto_clear(duration_ms)
        )

        return subtitle

    async def _auto_clear(self, delay_ms: int):
        """指定時間後に字幕をクリア"""
        try:
            await asyncio.sleep(delay_ms / 1000)
            await self.clear_subtitle()
        except asyncio.CancelledError:
            pass

    async def clear_subtitle(self):
        """字幕をクリア"""
        self._current_subtitle = None

        if self._on_clear:
            self._on_clear()

        logger.debug("Subtitle cleared")

    @property
    def current(self) -> Optional[LiveSubtitle]:
        """現在の字幕を取得"""
        return self._current_subtitle

    @property
    def history(self) -> list[LiveSubtitle]:
        """字幕履歴を取得"""
        return list(self._history)

    def export_history(self, format: str = "srt") -> str:
        """履歴をエクスポート

        Args:
            format: "srt" or "vtt"

        Returns:
            字幕ファイル内容
        """
        from .subtitle import SubtitleTrack

        track = SubtitleTrack(language="ja")

        # 履歴から字幕トラックを構築
        current_ms = 0
        for sub in self._history:
            track.add_entry(
                text=sub.text.replace("\n", " "),
                start_ms=current_ms,
                end_ms=current_ms + sub.duration_ms,
                speaker=sub.speaker if sub.speaker else None,
            )
            current_ms += sub.duration_ms + 200  # 200msのギャップ

        if format.lower() == "vtt":
            return track.to_vtt()
        return track.to_srt()

    def clear_history(self):
        """履歴をクリア"""
        self._history.clear()
        self._counter = 0


class SubtitleBroadcaster:
    """字幕ブロードキャスター

    WebSocket接続への字幕配信を管理。
    """

    def __init__(self):
        self._manager = LiveSubtitleManager()
        self._connections: list = []  # WebSocket connections

        # マネージャーにコールバック設定
        self._manager.set_subtitle_callback(self._broadcast_subtitle)
        self._manager.set_clear_callback(self._broadcast_clear)

    @property
    def manager(self) -> LiveSubtitleManager:
        """字幕マネージャーを取得"""
        return self._manager

    def add_connection(self, websocket):
        """WebSocket接続を追加"""
        if websocket not in self._connections:
            self._connections.append(websocket)
            logger.debug(f"Subtitle connection added. Total: {len(self._connections)}")

    def remove_connection(self, websocket):
        """WebSocket接続を削除"""
        if websocket in self._connections:
            self._connections.remove(websocket)
            logger.debug(f"Subtitle connection removed. Total: {len(self._connections)}")

    def _broadcast_subtitle(self, subtitle: LiveSubtitle):
        """字幕をブロードキャスト"""
        message = {
            "type": "subtitle",
            "action": "show",
            "data": subtitle.to_dict(),
        }
        asyncio.create_task(self._send_to_all(message))

    def _broadcast_clear(self):
        """クリアをブロードキャスト"""
        message = {
            "type": "subtitle",
            "action": "clear",
        }
        asyncio.create_task(self._send_to_all(message))

    async def _send_to_all(self, message: dict):
        """全接続にメッセージ送信"""
        disconnected = []

        for conn in self._connections:
            try:
                await conn.send_json(message)
            except Exception:
                disconnected.append(conn)

        for conn in disconnected:
            self.remove_connection(conn)


# グローバルインスタンス
subtitle_broadcaster = SubtitleBroadcaster()

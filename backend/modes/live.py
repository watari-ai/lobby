"""Live Mode - ライブ配信モード

OpenClaw Gateway + YouTube/Twitchコメント → AI応答 → TTS → アバター
"""

import asyncio
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Callable, Optional

from loguru import logger

from ..core.emotion import EmotionAnalyzer, EmotionResult
from ..core.live2d import Live2DLipsyncAnalyzer
from ..core.live_subtitle import LiveSubtitleManager, SubtitleConfig
from ..core.openclaw import LOBBY_SYSTEM_PROMPT, OpenClawClient, OpenClawConfig
from ..core.tts import TTSClient, TTSConfig
from ..integrations.twitch import TwitchChat, TwitchChatConfig, TwitchMessage
from ..integrations.youtube import YouTubeChat, YouTubeChatConfig, YouTubeComment


class InputSource(Enum):
    """入力ソース種別"""
    YOUTUBE_COMMENT = "youtube"
    TWITCH_COMMENT = "twitch"
    MICROPHONE = "microphone"
    MANUAL = "manual"  # テスト/デバッグ用


@dataclass
class LiveInput:
    """ライブ入力"""
    text: str
    source: InputSource
    author: str = "Anonymous"
    author_id: str = ""
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: dict = field(default_factory=dict)  # スパチャ金額など


@dataclass
class LiveOutput:
    """ライブ出力"""
    input: LiveInput
    response_text: str
    emotion: EmotionResult
    audio_path: Optional[Path] = None
    live2d_params: Optional[list] = None  # list[Live2DFrame]
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class LiveModeConfig:
    """ライブモード設定"""
    openclaw: OpenClawConfig = field(default_factory=OpenClawConfig)
    tts: TTSConfig = field(default_factory=TTSConfig)
    subtitle: SubtitleConfig = field(default_factory=SubtitleConfig)

    # キュー設定
    max_queue_size: int = 50
    process_interval: float = 0.5  # 処理間隔（秒）

    # フィルタリング
    min_input_length: int = 1
    max_input_length: int = 200
    blocked_words: list[str] = field(default_factory=list)

    # 出力設定
    audio_output_dir: Path = field(default_factory=lambda: Path("./output/live"))
    generate_live2d: bool = True
    generate_subtitles: bool = True  # リアルタイム字幕生成


class LiveMode:
    """ライブ配信モード

    入力キューからコメントを取り出し、
    OpenClaw → 感情分析 → TTS → Live2Dパラメータ
    のパイプラインで処理する。
    """

    def __init__(self, config: Optional[LiveModeConfig] = None):
        self.config = config or LiveModeConfig()

        # クライアント初期化
        self._openclaw = OpenClawClient(self.config.openclaw)
        self._tts = TTSClient(self.config.tts)
        self._emotion = EmotionAnalyzer()
        self._live2d: Optional[Live2DLipsyncAnalyzer] = None

        if self.config.generate_live2d:
            from ..core.live2d import Live2DConfig
            self._live2d = Live2DLipsyncAnalyzer(Live2DConfig())

        # 字幕マネージャー
        self._subtitle: Optional[LiveSubtitleManager] = None
        if self.config.generate_subtitles:
            self._subtitle = LiveSubtitleManager(self.config.subtitle)

        # 入力キュー
        self._input_queue: deque[LiveInput] = deque(maxlen=self.config.max_queue_size)

        # 状態
        self._running = False
        self._processing_task: Optional[asyncio.Task] = None

        # コールバック
        self._on_output: Optional[Callable[[LiveOutput], None]] = None
        self._on_error: Optional[Callable[[Exception], None]] = None

        # 出力ディレクトリ作成
        self.config.audio_output_dir.mkdir(parents=True, exist_ok=True)

    def set_system_prompt(self, prompt: str):
        """キャラクターのシステムプロンプト設定"""
        self._openclaw.set_system_prompt(prompt)

    def set_output_callback(self, callback: Callable[[LiveOutput], None]):
        """出力コールバック設定（WebSocket送信など）"""
        self._on_output = callback

    def set_error_callback(self, callback: Callable[[Exception], None]):
        """エラーコールバック設定"""
        self._on_error = callback

    @property
    def subtitle_manager(self) -> Optional[LiveSubtitleManager]:
        """字幕マネージャーを取得"""
        return self._subtitle

    def set_subtitle_callback(self, callback: Callable):
        """字幕コールバック設定"""
        if self._subtitle:
            self._subtitle.set_subtitle_callback(callback)

    def set_subtitle_clear_callback(self, callback: Callable):
        """字幕クリアコールバック設定"""
        if self._subtitle:
            self._subtitle.set_clear_callback(callback)

    def add_input(self, input_data: LiveInput) -> bool:
        """入力をキューに追加

        Returns:
            True if added, False if filtered/full
        """
        # フィルタリング
        if not self._should_process(input_data):
            logger.debug(f"Input filtered: {input_data.text[:30]}")
            return False

        # キュー追加
        try:
            self._input_queue.append(input_data)
            logger.info(f"Input queued: [{input_data.source.value}] {input_data.author}: {input_data.text[:30]}")
            return True
        except Exception:
            return False

    def _should_process(self, input_data: LiveInput) -> bool:
        """入力を処理すべきか判定"""
        text = input_data.text.strip()

        # 長さチェック
        if len(text) < self.config.min_input_length:
            return False
        if len(text) > self.config.max_input_length:
            return False

        # NGワードチェック
        text_lower = text.lower()
        for word in self.config.blocked_words:
            if word.lower() in text_lower:
                return False

        return True

    async def start(self):
        """処理ループ開始"""
        if self._running:
            return

        self._running = True
        self._processing_task = asyncio.create_task(self._process_loop())
        logger.info("Live mode started")

    async def stop(self):
        """処理ループ停止"""
        self._running = False
        if self._processing_task:
            self._processing_task.cancel()
            try:
                await self._processing_task
            except asyncio.CancelledError:
                pass
        logger.info("Live mode stopped")

    async def _process_loop(self):
        """メイン処理ループ"""
        while self._running:
            try:
                # キューから取得
                if self._input_queue:
                    input_data = self._input_queue.popleft()
                    await self._process_input(input_data)
                else:
                    await asyncio.sleep(self.config.process_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Process loop error: {e}")
                if self._on_error:
                    self._on_error(e)
                await asyncio.sleep(1.0)  # エラー時は少し待機

    async def _process_input(self, input_data: LiveInput):
        """1つの入力を処理"""
        logger.info(f"Processing: {input_data.text[:50]}")

        try:
            # 1. OpenClawでAI応答生成
            result = await self._openclaw.chat(input_data.text)
            response_text = result.text

            # 2. 感情分析
            emotion = self._emotion.analyze(response_text)

            # 3. TTS生成
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            audio_path = self.config.audio_output_dir / f"live_{timestamp}.mp3"
            await self._tts.synthesize(
                text=response_text,
                emotion=emotion.primary.value,
                output_path=audio_path,
            )

            # 4. Live2Dパラメータ生成
            live2d_params = None
            if self._live2d and audio_path.exists():
                live2d_params = self._live2d.analyze_audio(audio_path)

            # 5. リアルタイム字幕表示
            if self._subtitle:
                # 音声の長さに基づいて字幕表示時間を設定
                duration_ms = None
                if live2d_params:
                    # フレームの最後のタイムスタンプを使用
                    duration_ms = live2d_params[-1].timestamp_ms if live2d_params else None

                await self._subtitle.show_subtitle(
                    text=response_text,
                    speaker="",  # アバター名を設定可能
                    emotion=emotion.primary.value,
                    duration_ms=duration_ms,
                    metadata={
                        "input_author": input_data.author,
                        "input_text": input_data.text[:50],
                        "source": input_data.source.value,
                    },
                )

            # 出力オブジェクト作成
            output = LiveOutput(
                input=input_data,
                response_text=response_text,
                emotion=emotion,
                audio_path=audio_path,
                live2d_params=live2d_params,
            )

            # コールバック呼び出し
            if self._on_output:
                self._on_output(output)

            logger.info(f"Output ready: {response_text[:50]}")

        except Exception as e:
            logger.error(f"Failed to process input: {e}")
            if self._on_error:
                self._on_error(e)

    async def process_single(self, text: str, author: str = "User") -> LiveOutput:
        """単発処理（テスト/対話モード用）"""
        input_data = LiveInput(
            text=text,
            source=InputSource.MANUAL,
            author=author,
        )

        # 直接処理
        result = await self._openclaw.chat(text)
        emotion = self._emotion.analyze(result.text)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        audio_path = self.config.audio_output_dir / f"single_{timestamp}.mp3"
        await self._tts.synthesize(
            text=result.text,
            emotion=emotion.primary.value,
            output_path=audio_path,
        )

        live2d_params = None
        if self._live2d and audio_path.exists():
            live2d_params = self._live2d.analyze_audio(audio_path)

        # 字幕表示
        if self._subtitle:
            duration_ms = None
            if live2d_params:
                duration_ms = live2d_params[-1].timestamp_ms if live2d_params else None

            await self._subtitle.show_subtitle(
                text=result.text,
                emotion=emotion.primary.value,
                duration_ms=duration_ms,
            )

        return LiveOutput(
            input=input_data,
            response_text=result.text,
            emotion=emotion,
            audio_path=audio_path,
            live2d_params=live2d_params,
        )

    @property
    def queue_size(self) -> int:
        """現在のキューサイズ"""
        return len(self._input_queue)

    @property
    def is_running(self) -> bool:
        """実行中かどうか"""
        return self._running

    async def close(self):
        """リソース解放"""
        await self.stop()
        await self._openclaw.close()
        await self._tts.close()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()


class YouTubeLiveMode(LiveMode):
    """YouTube Live連携モード

    LiveModeにYouTubeコメント取得を統合。

    使用例:
    ```python
    async with YouTubeLiveMode(config) as live:
        await live.connect_youtube("VIDEO_ID", api_key="YOUR_API_KEY")
        await live.start()
        # コメントが自動的にキューに追加され処理される
    ```
    """

    def __init__(self, config: Optional[LiveModeConfig] = None):
        super().__init__(config)
        self._youtube: Optional[YouTubeChat] = None
        self._youtube_task: Optional[asyncio.Task] = None

        # スパチャ優先処理用
        self._priority_queue: deque[LiveInput] = deque(maxlen=20)

    async def connect_youtube(
        self,
        video_id_or_url: str,
        api_key: str,
        prioritize_super_chat: bool = True,
    ) -> bool:
        """YouTubeライブに接続

        Args:
            video_id_or_url: 動画ID または URL
            api_key: YouTube Data API v3キー
            prioritize_super_chat: スパチャを優先処理するか

        Returns:
            接続成功かどうか
        """
        yt_config = YouTubeChatConfig(api_key=api_key)
        self._youtube = YouTubeChat(yt_config)

        success = await self._youtube.connect(video_id_or_url)
        if not success:
            logger.error("Failed to connect to YouTube live chat")
            return False

        # コールバック設定
        if prioritize_super_chat:
            self._youtube.set_super_chat_callback(self._on_youtube_super_chat)
        self._youtube.set_comment_callback(self._on_youtube_comment)

        logger.info(f"Connected to YouTube: {video_id_or_url}")
        return True

    def _on_youtube_comment(self, comment: YouTubeComment):
        """通常コメント受信時"""
        live_input = LiveInput(
            text=comment.text,
            source=InputSource.YOUTUBE_COMMENT,
            author=comment.author_name,
            author_id=comment.author_channel_id,
            timestamp=comment.published_at,
            metadata={"profile_image": comment.author_profile_image},
        )
        self.add_input(live_input)

    def _on_youtube_super_chat(self, comment: YouTubeComment):
        """スパチャ/メンバーシップ受信時（優先キュー）"""
        metadata = {
            "profile_image": comment.author_profile_image,
            "type": comment.comment_type.value,
        }

        if comment.amount:
            metadata["amount"] = comment.amount
            metadata["currency"] = comment.currency

        if comment.membership_months:
            metadata["membership_months"] = comment.membership_months

        live_input = LiveInput(
            text=comment.text,
            source=InputSource.YOUTUBE_COMMENT,
            author=comment.author_name,
            author_id=comment.author_channel_id,
            timestamp=comment.published_at,
            metadata=metadata,
        )

        # 優先キューに追加
        self._priority_queue.append(live_input)
        logger.info(f"[SuperChat] {comment.author_name}: {comment.text} ({comment.amount} {comment.currency})")

    async def start(self):
        """処理ループ + YouTubeストリーム開始"""
        if self._youtube:
            self._youtube_task = asyncio.create_task(self._youtube_stream_loop())
        await super().start()

    async def _youtube_stream_loop(self):
        """YouTubeコメントストリームループ"""
        try:
            async for comment in self._youtube.stream():
                if not self._running:
                    break
                # コールバック内で処理済み
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"YouTube stream error: {e}")

    async def _process_loop(self):
        """メイン処理ループ（スパチャ優先）"""
        while self._running:
            try:
                # 優先キュー（スパチャ）を先に処理
                if self._priority_queue:
                    input_data = self._priority_queue.popleft()
                    await self._process_input(input_data)
                # 通常キュー
                elif self._input_queue:
                    input_data = self._input_queue.popleft()
                    await self._process_input(input_data)
                else:
                    await asyncio.sleep(self.config.process_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Process loop error: {e}")
                if self._on_error:
                    self._on_error(e)
                await asyncio.sleep(1.0)

    async def stop(self):
        """全ループ停止"""
        if self._youtube:
            self._youtube.stop()
        if self._youtube_task:
            self._youtube_task.cancel()
            try:
                await self._youtube_task
            except asyncio.CancelledError:
                pass
        await super().stop()

    async def close(self):
        """リソース解放"""
        await self.stop()
        if self._youtube:
            await self._youtube.close()
        await super().close()


class TwitchLiveMode(LiveMode):
    """Twitch連携モード

    LiveModeにTwitchチャット取得を統合。

    使用例:
    ```python
    async with TwitchLiveMode(config) as live:
        await live.connect_twitch("channel_name", oauth_token="oauth:xxx")
        await live.start()
        # コメントが自動的にキューに追加され処理される
    ```

    匿名接続（読み取り専用）:
    ```python
    async with TwitchLiveMode(config) as live:
        await live.connect_twitch("channel_name")  # OAuth不要
        await live.start()
    ```
    """

    def __init__(self, config: Optional[LiveModeConfig] = None):
        super().__init__(config)
        self._twitch: Optional[TwitchChat] = None
        self._twitch_task: Optional[asyncio.Task] = None

        # Bits/サブスク優先処理用
        self._priority_queue: deque[LiveInput] = deque(maxlen=20)

    async def connect_twitch(
        self,
        channel: str,
        oauth_token: str = "",
        nick: str = "justinfan12345",
        prioritize_bits: bool = True,
    ) -> bool:
        """Twitchチャンネルに接続

        Args:
            channel: チャンネル名（# なし）
            oauth_token: OAuth トークン（空の場合は匿名接続）
            nick: ボット名（匿名接続の場合は justinfan12345）
            prioritize_bits: Bits/サブスクを優先処理するか

        Returns:
            接続成功かどうか
        """
        twitch_config = TwitchChatConfig(
            oauth_token=oauth_token,
            nick=nick,
            channel=channel,
        )
        self._twitch = TwitchChat(twitch_config)

        success = await self._twitch.connect()
        if not success:
            logger.error("Failed to connect to Twitch chat")
            return False

        # コールバック設定
        self._twitch.set_message_callback(self._on_twitch_message)
        if prioritize_bits:
            self._twitch.set_bits_callback(self._on_twitch_bits)
            self._twitch.set_sub_callback(self._on_twitch_sub)
            self._twitch.set_raid_callback(self._on_twitch_raid)

        logger.info(f"Connected to Twitch: #{channel}")
        return True

    def _on_twitch_message(self, message: TwitchMessage):
        """通常メッセージ受信時"""
        live_input = LiveInput(
            text=message.text,
            source=InputSource.TWITCH_COMMENT,
            author=message.author_display_name,
            author_id=message.author_id,
            timestamp=message.timestamp,
            metadata={
                "badges": [b.name for b in message.badges],
                "emotes": [e.name for e in message.emotes],
                "color": message.color,
                "is_subscriber": message.is_subscriber,
                "is_moderator": message.is_moderator,
                "is_vip": message.is_vip,
            },
        )
        self.add_input(live_input)

    def _on_twitch_bits(self, message: TwitchMessage):
        """Bits受信時（優先キュー）"""
        live_input = LiveInput(
            text=message.text,
            source=InputSource.TWITCH_COMMENT,
            author=message.author_display_name,
            author_id=message.author_id,
            timestamp=message.timestamp,
            metadata={
                "type": "bits",
                "bits": message.bits,
                "badges": [b.name for b in message.badges],
            },
        )
        self._priority_queue.append(live_input)
        logger.info(f"[Bits] {message.author_display_name}: {message.text} ({message.bits} bits)")

    def _on_twitch_sub(self, message: TwitchMessage):
        """サブスク受信時（優先キュー）"""
        live_input = LiveInput(
            text=message.text or "サブスクありがとう！",
            source=InputSource.TWITCH_COMMENT,
            author=message.author_display_name,
            author_id=message.author_id,
            timestamp=message.timestamp,
            metadata={
                "type": message.message_type.value,
                "sub_months": message.sub_months,
                "sub_tier": message.sub_tier,
            },
        )
        self._priority_queue.append(live_input)
        logger.info(f"[Sub] {message.author_display_name}: {message.sub_months}ヶ月 (Tier {message.sub_tier})")

    def _on_twitch_raid(self, message: TwitchMessage):
        """レイド受信時（優先キュー）"""
        live_input = LiveInput(
            text=f"レイドありがとう！{message.raid_viewer_count}人も来てくれたっす！",
            source=InputSource.TWITCH_COMMENT,
            author=message.author_display_name,
            author_id=message.author_id,
            timestamp=message.timestamp,
            metadata={
                "type": "raid",
                "viewer_count": message.raid_viewer_count,
            },
        )
        self._priority_queue.append(live_input)
        logger.info(f"[Raid] {message.author_display_name}: {message.raid_viewer_count}人")

    async def start(self):
        """処理ループ + Twitchストリーム開始"""
        if self._twitch:
            self._twitch_task = asyncio.create_task(self._twitch_stream_loop())
        await super().start()

    async def _twitch_stream_loop(self):
        """Twitchチャットストリームループ"""
        try:
            async for message in self._twitch.stream():
                if not self._running:
                    break
                # コールバック内で処理済み
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Twitch stream error: {e}")

    async def _process_loop(self):
        """メイン処理ループ（Bits/サブスク優先）"""
        while self._running:
            try:
                # 優先キュー（Bits/サブスク）を先に処理
                if self._priority_queue:
                    input_data = self._priority_queue.popleft()
                    await self._process_input(input_data)
                # 通常キュー
                elif self._input_queue:
                    input_data = self._input_queue.popleft()
                    await self._process_input(input_data)
                else:
                    await asyncio.sleep(self.config.process_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Process loop error: {e}")
                if self._on_error:
                    self._on_error(e)
                await asyncio.sleep(1.0)

    async def stop(self):
        """全ループ停止"""
        if self._twitch:
            self._twitch.stop()
        if self._twitch_task:
            self._twitch_task.cancel()
            try:
                await self._twitch_task
            except asyncio.CancelledError:
                pass
        await super().stop()

    async def close(self):
        """リソース解放"""
        await self.stop()
        if self._twitch:
            await self._twitch.close()
        await super().close()


async def create_lobby_live_mode(
    gateway_url: str = "http://localhost:18789",
    tts_url: str = "http://localhost:8001",
) -> LiveMode:
    """ロビィ用ライブモード生成"""
    config = LiveModeConfig(
        openclaw=OpenClawConfig(
            base_url=gateway_url,
            system_prompt=LOBBY_SYSTEM_PROMPT,
            temperature=0.9,
            max_tokens=200,
        ),
        tts=TTSConfig(
            base_url=tts_url,
            voice="lobby",
        ),
    )
    return LiveMode(config)


async def create_lobby_youtube_mode(
    gateway_url: str = "http://localhost:18789",
    tts_url: str = "http://localhost:8001",
) -> YouTubeLiveMode:
    """ロビィ用YouTubeライブモード生成"""
    config = LiveModeConfig(
        openclaw=OpenClawConfig(
            base_url=gateway_url,
            system_prompt=LOBBY_SYSTEM_PROMPT,
            temperature=0.9,
            max_tokens=200,
        ),
        tts=TTSConfig(
            base_url=tts_url,
            voice="lobby",
        ),
    )
    return YouTubeLiveMode(config)


async def create_lobby_twitch_mode(
    gateway_url: str = "http://localhost:18789",
    tts_url: str = "http://localhost:8001",
) -> TwitchLiveMode:
    """ロビィ用Twitchライブモード生成"""
    config = LiveModeConfig(
        openclaw=OpenClawConfig(
            base_url=gateway_url,
            system_prompt=LOBBY_SYSTEM_PROMPT,
            temperature=0.9,
            max_tokens=200,
        ),
        tts=TTSConfig(
            base_url=tts_url,
            voice="lobby",
        ),
    )
    return TwitchLiveMode(config)

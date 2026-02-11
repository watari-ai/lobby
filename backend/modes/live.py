"""Live Mode - ライブ配信モード

OpenClaw Gateway + YouTube/Twitchコメント → AI応答 → TTS → アバター
"""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import AsyncIterator, Callable, Optional
from collections import deque

from loguru import logger

from ..core.openclaw import OpenClawClient, OpenClawConfig, LOBBY_SYSTEM_PROMPT
from ..core.tts import TTSClient, TTSConfig
from ..core.emotion import EmotionAnalyzer, EmotionResult
from ..core.live2d import Live2DLipsyncAnalyzer, Live2DParameters
from ..integrations.youtube import YouTubeChat, YouTubeChatConfig, YouTubeComment, CommentType


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

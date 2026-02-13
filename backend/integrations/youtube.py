"""YouTube Live Chat Integration

YouTube Data API v3を使用してライブチャットコメントを取得する。

使用方法:
1. Google Cloud Consoleでプロジェクト作成
2. YouTube Data API v3を有効化
3. OAuth 2.0クライアントIDを作成（デスクトップアプリ）
4. credentials.jsonをダウンロードしてconfig/に配置

参考:
- https://developers.google.com/youtube/v3/live/docs/liveChatMessages/list
"""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import AsyncIterator, Callable, Optional

import aiohttp
from loguru import logger


class YouTubeAuthMethod(Enum):
    """認証方式"""
    API_KEY = "api_key"  # 読み取り専用（公開配信のみ）
    OAUTH = "oauth"  # フル機能（非公開配信も可）


class CommentType(Enum):
    """コメント種別"""
    TEXT = "textMessageEvent"
    SUPER_CHAT = "superChatEvent"
    SUPER_STICKER = "superStickerEvent"
    MEMBERSHIP = "newSponsorEvent"
    MEMBER_MILESTONE = "memberMilestoneChatEvent"


@dataclass
class YouTubeComment:
    """YouTubeライブコメント"""
    id: str
    text: str
    author_name: str
    author_channel_id: str
    author_profile_image: str
    published_at: datetime
    comment_type: CommentType

    # Super Chat/Sticker
    amount: Optional[float] = None
    currency: Optional[str] = None

    # メンバーシップ
    membership_months: Optional[int] = None

    # 生データ
    raw: dict = field(default_factory=dict)

    @classmethod
    def from_api_response(cls, item: dict) -> "YouTubeComment":
        """API応答からコメントオブジェクトを生成"""
        snippet = item.get("snippet", {})
        author = item.get("authorDetails", {})

        # コメント種別判定
        comment_type = CommentType.TEXT
        if "superChatDetails" in snippet:
            comment_type = CommentType.SUPER_CHAT
        elif "superStickerDetails" in snippet:
            comment_type = CommentType.SUPER_STICKER
        elif snippet.get("type") == "newSponsorEvent":
            comment_type = CommentType.MEMBERSHIP
        elif snippet.get("type") == "memberMilestoneChatEvent":
            comment_type = CommentType.MEMBER_MILESTONE

        # テキスト抽出
        text = ""
        if comment_type == CommentType.TEXT:
            text = snippet.get("textMessageDetails", {}).get("messageText", "")
        elif comment_type == CommentType.SUPER_CHAT:
            details = snippet.get("superChatDetails", {})
            text = details.get("userComment", "")
        elif comment_type == CommentType.SUPER_STICKER:
            text = "[Super Sticker]"
        elif comment_type in (CommentType.MEMBERSHIP, CommentType.MEMBER_MILESTONE):
            text = snippet.get("userComment", "[メンバーシップ登録ありがとうございます！]")

        # Super Chat金額
        amount = None
        currency = None
        if comment_type == CommentType.SUPER_CHAT:
            details = snippet.get("superChatDetails", {})
            amount = float(details.get("amountMicros", 0)) / 1_000_000
            currency = details.get("currency", "JPY")
        elif comment_type == CommentType.SUPER_STICKER:
            details = snippet.get("superStickerDetails", {})
            amount = float(details.get("amountMicros", 0)) / 1_000_000
            currency = details.get("currency", "JPY")

        # メンバーシップ月数
        membership_months = None
        if comment_type == CommentType.MEMBER_MILESTONE:
            membership_months = snippet.get("memberMilestoneChatDetails", {}).get("memberMonth", 0)

        return cls(
            id=item.get("id", ""),
            text=text,
            author_name=author.get("displayName", "Unknown"),
            author_channel_id=author.get("channelId", ""),
            author_profile_image=author.get("profileImageUrl", ""),
            published_at=datetime.fromisoformat(
                snippet.get("publishedAt", "").replace("Z", "+00:00")
            ) if snippet.get("publishedAt") else datetime.now(),
            comment_type=comment_type,
            amount=amount,
            currency=currency,
            membership_months=membership_months,
            raw=item,
        )


@dataclass
class YouTubeChatConfig:
    """YouTube Live Chat設定"""

    # 認証
    auth_method: YouTubeAuthMethod = YouTubeAuthMethod.API_KEY
    api_key: Optional[str] = None
    credentials_path: Path = Path("config/youtube_credentials.json")
    token_path: Path = Path("config/youtube_token.json")

    # ポーリング設定
    poll_interval: float = 2.0  # API推奨: 最小2秒
    max_results: int = 200  # 1リクエストあたりの最大取得数

    # フィルタリング
    include_super_chat: bool = True
    include_super_sticker: bool = True
    include_membership: bool = True

    # API URL
    api_base: str = "https://www.googleapis.com/youtube/v3"


class YouTubeChat:
    """YouTubeライブチャット取得クライアント

    使用例:
    ```python
    async with YouTubeChat(config) as chat:
        await chat.connect("VIDEO_ID_OR_URL")

        async for comment in chat.stream():
            print(f"{comment.author_name}: {comment.text}")
    ```
    """

    def __init__(self, config: Optional[YouTubeChatConfig] = None):
        self.config = config or YouTubeChatConfig()
        self._session: Optional[aiohttp.ClientSession] = None
        self._live_chat_id: Optional[str] = None
        self._next_page_token: Optional[str] = None
        self._running = False

        # コールバック
        self._on_comment: Optional[Callable[[YouTubeComment], None]] = None
        self._on_super_chat: Optional[Callable[[YouTubeComment], None]] = None
        self._on_error: Optional[Callable[[Exception], None]] = None

    def set_comment_callback(self, callback: Callable[[YouTubeComment], None]):
        """通常コメントコールバック"""
        self._on_comment = callback

    def set_super_chat_callback(self, callback: Callable[[YouTubeComment], None]):
        """スパチャ/メンバーシップコールバック"""
        self._on_super_chat = callback

    def set_error_callback(self, callback: Callable[[Exception], None]):
        """エラーコールバック"""
        self._on_error = callback

    async def _ensure_session(self):
        """セッション確保"""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()

    async def connect(self, video_id_or_url: str) -> bool:
        """配信に接続

        Args:
            video_id_or_url: 動画ID または URL

        Returns:
            接続成功かどうか
        """
        await self._ensure_session()

        # URLから動画ID抽出
        video_id = self._extract_video_id(video_id_or_url)
        if not video_id:
            logger.error(f"Invalid video ID or URL: {video_id_or_url}")
            return False

        # ライブチャットID取得
        self._live_chat_id = await self._get_live_chat_id(video_id)
        if not self._live_chat_id:
            logger.error(f"Could not get live chat ID for video: {video_id}")
            return False

        logger.info(f"Connected to YouTube live chat: {self._live_chat_id}")
        return True

    def _extract_video_id(self, video_id_or_url: str) -> Optional[str]:
        """URLから動画IDを抽出"""
        import re

        # 既に動画IDの場合
        if re.match(r'^[a-zA-Z0-9_-]{11}$', video_id_or_url):
            return video_id_or_url

        # URL パターン
        patterns = [
            r'(?:youtube\.com/watch\?v=|youtu\.be/)([a-zA-Z0-9_-]{11})',
            r'youtube\.com/live/([a-zA-Z0-9_-]{11})',
        ]

        for pattern in patterns:
            match = re.search(pattern, video_id_or_url)
            if match:
                return match.group(1)

        return None

    async def _get_live_chat_id(self, video_id: str) -> Optional[str]:
        """動画IDからライブチャットIDを取得"""
        url = f"{self.config.api_base}/videos"
        params = {
            "part": "liveStreamingDetails",
            "id": video_id,
            "key": self.config.api_key,
        }

        try:
            async with self._session.get(url, params=params) as resp:
                if resp.status != 200:
                    error_text = await resp.text()
                    logger.error(f"YouTube API error: {resp.status} - {error_text}")
                    return None

                data = await resp.json()
                items = data.get("items", [])
                if not items:
                    logger.error(f"Video not found: {video_id}")
                    return None

                live_details = items[0].get("liveStreamingDetails", {})
                chat_id = live_details.get("activeLiveChatId")

                if not chat_id:
                    logger.error(f"Video is not a live stream or chat is disabled: {video_id}")
                    return None

                return chat_id

        except Exception as e:
            logger.error(f"Failed to get live chat ID: {e}")
            return None

    async def fetch_comments(self) -> list[YouTubeComment]:
        """コメントを取得（1回分）"""
        if not self._live_chat_id:
            raise RuntimeError("Not connected to a live chat. Call connect() first.")

        await self._ensure_session()

        url = f"{self.config.api_base}/liveChat/messages"
        params = {
            "liveChatId": self._live_chat_id,
            "part": "snippet,authorDetails",
            "maxResults": self.config.max_results,
            "key": self.config.api_key,
        }

        if self._next_page_token:
            params["pageToken"] = self._next_page_token

        try:
            async with self._session.get(url, params=params) as resp:
                if resp.status != 200:
                    error_text = await resp.text()
                    logger.error(f"YouTube API error: {resp.status} - {error_text}")
                    return []

                data = await resp.json()

                # 次ページトークン保存
                self._next_page_token = data.get("nextPageToken")

                # ポーリング間隔更新（API推奨値を使用）
                poll_interval_ms = data.get("pollingIntervalMillis", 2000)
                self.config.poll_interval = max(poll_interval_ms / 1000, 2.0)

                # コメント解析
                comments = []
                for item in data.get("items", []):
                    try:
                        comment = YouTubeComment.from_api_response(item)
                        comments.append(comment)
                    except Exception as e:
                        logger.warning(f"Failed to parse comment: {e}")

                return comments

        except Exception as e:
            logger.error(f"Failed to fetch comments: {e}")
            if self._on_error:
                self._on_error(e)
            return []

    async def stream(self) -> AsyncIterator[YouTubeComment]:
        """コメントストリーム（ジェネレータ）"""
        self._running = True

        while self._running:
            comments = await self.fetch_comments()

            for comment in comments:
                yield comment

                # コールバック呼び出し
                if comment.comment_type in (
                    CommentType.SUPER_CHAT,
                    CommentType.SUPER_STICKER,
                    CommentType.MEMBERSHIP,
                    CommentType.MEMBER_MILESTONE,
                ):
                    if self._on_super_chat:
                        self._on_super_chat(comment)
                else:
                    if self._on_comment:
                        self._on_comment(comment)

            # ポーリング間隔待機
            await asyncio.sleep(self.config.poll_interval)

    def stop(self):
        """ストリーム停止"""
        self._running = False

    async def close(self):
        """リソース解放"""
        self.stop()
        if self._session and not self._session.closed:
            await self._session.close()

    async def __aenter__(self):
        await self._ensure_session()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()


class YouTubeChatMock:
    """テスト用モック

    API キーなしでYouTubeChat互換のインターフェースを提供。
    """

    def __init__(self, comments: Optional[list[dict]] = None):
        self._comments = comments or [
            {"author": "テストユーザー1", "text": "おはロビィ！"},
            {"author": "テストユーザー2", "text": "かわいい！"},
            {"author": "スパチャさん", "text": "頑張って！", "amount": 500, "currency": "JPY"},
        ]
        self._index = 0
        self._running = False

    async def connect(self, video_id: str) -> bool:
        logger.info(f"[Mock] Connected to video: {video_id}")
        return True

    async def stream(self) -> AsyncIterator[YouTubeComment]:
        self._running = True

        while self._running and self._index < len(self._comments):
            data = self._comments[self._index]
            self._index += 1

            comment = YouTubeComment(
                id=f"mock_{self._index}",
                text=data.get("text", ""),
                author_name=data.get("author", "MockUser"),
                author_channel_id="UC_MOCK",
                author_profile_image="",
                published_at=datetime.now(),
                comment_type=CommentType.SUPER_CHAT if data.get("amount") else CommentType.TEXT,
                amount=data.get("amount"),
                currency=data.get("currency"),
            )

            yield comment
            await asyncio.sleep(1.0)  # 1秒ごとに1コメント

    def stop(self):
        self._running = False

    async def close(self):
        self.stop()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

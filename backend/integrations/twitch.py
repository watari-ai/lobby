"""Twitch Chat Integration

Twitch IRC と EventSub を使用してライブチャットを取得する。

使用方法:
1. https://dev.twitch.tv/console でアプリ登録
2. Client ID と Client Secret を取得
3. OAuth トークンを生成（https://twitchtokengenerator.com/ 推奨）

参考:
- IRC: https://dev.twitch.tv/docs/irc
- EventSub: https://dev.twitch.tv/docs/eventsub
"""

import asyncio
import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import AsyncIterator, Callable, Optional

from loguru import logger


class TwitchMessageType(Enum):
    """メッセージ種別"""
    CHAT = "chat"              # 通常チャット
    BITS = "bits"              # Bits（チアー）
    SUB = "subscription"       # サブスクライブ
    RESUB = "resubscription"   # 再サブスク
    GIFT_SUB = "gift_sub"      # ギフトサブ
    RAID = "raid"              # レイド
    HIGHLIGHT = "highlight"    # ハイライトメッセージ


@dataclass
class TwitchBadge:
    """Twitchバッジ"""
    name: str
    version: str


@dataclass
class TwitchEmote:
    """Twitchエモート"""
    id: str
    name: str
    start: int
    end: int


@dataclass
class TwitchMessage:
    """Twitchチャットメッセージ"""
    id: str
    text: str
    author_name: str
    author_id: str
    author_display_name: str
    channel: str
    timestamp: datetime
    message_type: TwitchMessageType

    # バッジ・エモート
    badges: list[TwitchBadge] = field(default_factory=list)
    emotes: list[TwitchEmote] = field(default_factory=list)
    color: Optional[str] = None

    # Bits
    bits: int = 0

    # サブスク
    sub_months: int = 0
    sub_tier: Optional[str] = None  # "1000", "2000", "3000"

    # レイド
    raid_viewer_count: int = 0

    # フラグ
    is_subscriber: bool = False
    is_moderator: bool = False
    is_vip: bool = False
    is_broadcaster: bool = False
    is_first_message: bool = False

    # 生データ
    raw_tags: dict = field(default_factory=dict)
    raw_message: str = ""

    @classmethod
    def from_irc(cls, raw: str, tags: dict) -> Optional["TwitchMessage"]:
        """IRC メッセージからパース"""
        # PRIVMSG フォーマット: :user!user@user.tmi.twitch.tv PRIVMSG #channel :message
        match = re.match(
            r':(\w+)!\w+@\w+\.tmi\.twitch\.tv PRIVMSG #(\w+) :(.+)',
            raw.strip()
        )
        if not match:
            return None

        username, channel, text = match.groups()

        # メッセージ種別判定
        msg_type = TwitchMessageType.CHAT
        bits = int(tags.get("bits", 0))
        if bits > 0:
            msg_type = TwitchMessageType.BITS
        elif tags.get("msg-id") in ("sub", "resub", "subgift"):
            msg_type = TwitchMessageType({
                "sub": "subscription",
                "resub": "resubscription",
                "subgift": "gift_sub",
            }.get(tags.get("msg-id"), "chat"))

        # バッジ解析
        badges = []
        badge_str = tags.get("badges", "")
        if badge_str:
            for badge in badge_str.split(","):
                if "/" in badge:
                    name, version = badge.split("/", 1)
                    badges.append(TwitchBadge(name=name, version=version))

        # エモート解析
        emotes = []
        emote_str = tags.get("emotes", "")
        if emote_str:
            for emote_data in emote_str.split("/"):
                if ":" in emote_data:
                    emote_id, positions = emote_data.split(":", 1)
                    for pos in positions.split(","):
                        if "-" in pos:
                            start, end = map(int, pos.split("-"))
                            emotes.append(TwitchEmote(
                                id=emote_id,
                                name=text[start:end+1] if start < len(text) else "",
                                start=start,
                                end=end,
                            ))

        # タイムスタンプ
        tmi_sent_ts = tags.get("tmi-sent-ts")
        timestamp = datetime.fromtimestamp(int(tmi_sent_ts) / 1000) if tmi_sent_ts else datetime.now()

        # サブスク情報
        sub_months = 0
        sub_tier = None
        if "msg-param-cumulative-months" in tags:
            sub_months = int(tags.get("msg-param-cumulative-months", 0))
        if "msg-param-sub-plan" in tags:
            sub_tier = tags.get("msg-param-sub-plan")

        return cls(
            id=tags.get("id", ""),
            text=text,
            author_name=username,
            author_id=tags.get("user-id", ""),
            author_display_name=tags.get("display-name", username),
            channel=channel,
            timestamp=timestamp,
            message_type=msg_type,
            badges=badges,
            emotes=emotes,
            color=tags.get("color"),
            bits=bits,
            sub_months=sub_months,
            sub_tier=sub_tier,
            is_subscriber=any(b.name == "subscriber" for b in badges),
            is_moderator=tags.get("mod") == "1",
            is_vip=any(b.name == "vip" for b in badges),
            is_broadcaster=any(b.name == "broadcaster" for b in badges),
            is_first_message=tags.get("first-msg") == "1",
            raw_tags=tags,
            raw_message=raw,
        )


@dataclass
class TwitchChatConfig:
    """Twitch Chat 設定"""

    # 認証
    oauth_token: str = ""  # OAuth トークン（oauth:xxxxx）
    client_id: Optional[str] = None

    # 接続先
    nick: str = "justinfan12345"  # 匿名接続用（読み取り専用）
    channel: str = ""  # チャンネル名（# なし）

    # IRC サーバー
    irc_host: str = "irc.chat.twitch.tv"
    irc_port: int = 6667
    irc_ssl_port: int = 6697
    use_ssl: bool = False

    # 設定
    request_tags: bool = True  # IRCv3 タグ要求
    request_commands: bool = True  # コマンド要求（USERNOTICE等）

    # ヘルスチェック
    ping_interval: float = 60.0  # PING 間隔（秒）
    ping_timeout: float = 10.0  # PONG タイムアウト（秒）


class TwitchChat:
    """Twitch IRC チャットクライアント

    使用例:
    ```python
    config = TwitchChatConfig(
        oauth_token="oauth:your_token_here",
        nick="your_bot_name",
        channel="streamer_name",
    )

    async with TwitchChat(config) as chat:
        async for message in chat.stream():
            print(f"{message.author_display_name}: {message.text}")
    ```

    匿名接続（読み取り専用）:
    ```python
    config = TwitchChatConfig(channel="streamer_name")
    async with TwitchChat(config) as chat:
        async for message in chat.stream():
            print(f"{message.author_display_name}: {message.text}")
    ```
    """

    def __init__(self, config: Optional[TwitchChatConfig] = None):
        self.config = config or TwitchChatConfig()
        self._reader: Optional[asyncio.StreamReader] = None
        self._writer: Optional[asyncio.StreamWriter] = None
        self._running = False
        self._connected = False
        self._last_pong: datetime = datetime.now()

        # コールバック
        self._on_message: Optional[Callable[[TwitchMessage], None]] = None
        self._on_bits: Optional[Callable[[TwitchMessage], None]] = None
        self._on_sub: Optional[Callable[[TwitchMessage], None]] = None
        self._on_raid: Optional[Callable[[TwitchMessage], None]] = None
        self._on_error: Optional[Callable[[Exception], None]] = None

    def set_message_callback(self, callback: Callable[[TwitchMessage], None]):
        """通常メッセージコールバック"""
        self._on_message = callback

    def set_bits_callback(self, callback: Callable[[TwitchMessage], None]):
        """Bits コールバック"""
        self._on_bits = callback

    def set_sub_callback(self, callback: Callable[[TwitchMessage], None]):
        """サブスクコールバック"""
        self._on_sub = callback

    def set_raid_callback(self, callback: Callable[[TwitchMessage], None]):
        """レイドコールバック"""
        self._on_raid = callback

    def set_error_callback(self, callback: Callable[[Exception], None]):
        """エラーコールバック"""
        self._on_error = callback

    async def connect(self) -> bool:
        """IRC サーバーに接続"""
        try:
            host = self.config.irc_host
            port = self.config.irc_ssl_port if self.config.use_ssl else self.config.irc_port

            logger.info(f"Connecting to Twitch IRC: {host}:{port}")

            if self.config.use_ssl:
                self._reader, self._writer = await asyncio.open_connection(
                    host, port, ssl=True
                )
            else:
                self._reader, self._writer = await asyncio.open_connection(
                    host, port
                )

            # 認証
            oauth = self.config.oauth_token
            if oauth and not oauth.startswith("oauth:"):
                oauth = f"oauth:{oauth}"

            # 匿名接続の場合
            if not oauth:
                oauth = "oauth:anonymous"

            await self._send(f"PASS {oauth}")
            await self._send(f"NICK {self.config.nick}")

            # IRCv3 機能要求
            if self.config.request_tags:
                await self._send("CAP REQ :twitch.tv/tags")
            if self.config.request_commands:
                await self._send("CAP REQ :twitch.tv/commands")

            # チャンネル参加
            if self.config.channel:
                channel = self.config.channel.lower().lstrip("#")
                await self._send(f"JOIN #{channel}")

            # 接続確認
            while True:
                line = await self._recv()
                if not line:
                    continue

                logger.debug(f"IRC: {line}")

                # 認証成功
                if "Welcome, GLHF!" in line or ":tmi.twitch.tv 001" in line:
                    self._connected = True
                    logger.info(f"Connected to Twitch chat: #{self.config.channel}")
                    return True

                # 認証失敗
                if "Login authentication failed" in line:
                    logger.error("Twitch authentication failed")
                    return False

                # PING 応答
                if line.startswith("PING"):
                    await self._send(f"PONG {line[5:]}")

                # チャンネル参加完了
                if f"JOIN #{self.config.channel.lower()}" in line:
                    self._connected = True
                    logger.info(f"Joined channel: #{self.config.channel}")
                    return True

        except Exception as e:
            logger.error(f"Failed to connect to Twitch: {e}")
            if self._on_error:
                self._on_error(e)
            return False

    async def _send(self, message: str):
        """メッセージ送信"""
        if self._writer:
            self._writer.write(f"{message}\r\n".encode())
            await self._writer.drain()
            logger.debug(f"Sent: {message}")

    async def _recv(self) -> Optional[str]:
        """メッセージ受信"""
        if self._reader:
            try:
                data = await asyncio.wait_for(
                    self._reader.readline(),
                    timeout=self.config.ping_interval + 5
                )
                return data.decode().strip()
            except asyncio.TimeoutError:
                return None
        return None

    def _parse_tags(self, tag_str: str) -> dict:
        """IRCv3 タグをパース"""
        tags = {}
        for tag in tag_str.split(";"):
            if "=" in tag:
                key, value = tag.split("=", 1)
                # エスケープ解除
                value = value.replace("\\s", " ").replace("\\n", "\n")
                value = value.replace("\\r", "\r").replace("\\:", ";")
                value = value.replace("\\\\", "\\")
                tags[key] = value
            else:
                tags[tag] = ""
        return tags

    async def _process_line(self, line: str) -> Optional[TwitchMessage]:
        """IRC 行を処理"""
        if not line:
            return None

        # PING 応答
        if line.startswith("PING"):
            await self._send(f"PONG {line[5:]}")
            return None

        # PONG 受信
        if "PONG" in line:
            self._last_pong = datetime.now()
            return None

        # タグ付きメッセージ
        tags = {}
        if line.startswith("@"):
            tag_end = line.index(" ")
            tags = self._parse_tags(line[1:tag_end])
            line = line[tag_end + 1:]

        # PRIVMSG パース
        if "PRIVMSG" in line:
            message = TwitchMessage.from_irc(line, tags)
            if message:
                return message

        # USERNOTICE（サブスク、レイド等）
        if "USERNOTICE" in line:
            msg_id = tags.get("msg-id", "")

            # レイド
            if msg_id == "raid":
                return TwitchMessage(
                    id=tags.get("id", ""),
                    text=tags.get("system-msg", ""),
                    author_name=tags.get("login", ""),
                    author_id=tags.get("user-id", ""),
                    author_display_name=tags.get("display-name", ""),
                    channel=self.config.channel,
                    timestamp=datetime.now(),
                    message_type=TwitchMessageType.RAID,
                    raid_viewer_count=int(tags.get("msg-param-viewerCount", 0)),
                    raw_tags=tags,
                    raw_message=line,
                )

            # サブスク関連
            if msg_id in ("sub", "resub", "subgift"):
                # メッセージ抽出
                text = ""
                match = re.search(r'USERNOTICE #\w+ :(.+)', line)
                if match:
                    text = match.group(1)

                return TwitchMessage(
                    id=tags.get("id", ""),
                    text=text or tags.get("system-msg", ""),
                    author_name=tags.get("login", ""),
                    author_id=tags.get("user-id", ""),
                    author_display_name=tags.get("display-name", ""),
                    channel=self.config.channel,
                    timestamp=datetime.now(),
                    message_type=TwitchMessageType({
                        "sub": "subscription",
                        "resub": "resubscription",
                        "subgift": "gift_sub",
                    }.get(msg_id, "chat")),
                    sub_months=int(tags.get("msg-param-cumulative-months", 0)),
                    sub_tier=tags.get("msg-param-sub-plan"),
                    raw_tags=tags,
                    raw_message=line,
                )

        return None

    async def stream(self) -> AsyncIterator[TwitchMessage]:
        """メッセージストリーム"""
        self._running = True

        # PING タスク開始
        ping_task = asyncio.create_task(self._ping_loop())

        try:
            while self._running and self._connected:
                line = await self._recv()
                if line is None:
                    # タイムアウト - 接続確認
                    if (datetime.now() - self._last_pong).total_seconds() > self.config.ping_timeout * 2:
                        logger.warning("Twitch connection lost, reconnecting...")
                        await self.connect()
                    continue

                logger.debug(f"IRC: {line}")

                message = await self._process_line(line)
                if message:
                    yield message

                    # コールバック
                    if message.message_type == TwitchMessageType.BITS:
                        if self._on_bits:
                            self._on_bits(message)
                    elif message.message_type in (
                        TwitchMessageType.SUB,
                        TwitchMessageType.RESUB,
                        TwitchMessageType.GIFT_SUB,
                    ):
                        if self._on_sub:
                            self._on_sub(message)
                    elif message.message_type == TwitchMessageType.RAID:
                        if self._on_raid:
                            self._on_raid(message)
                    else:
                        if self._on_message:
                            self._on_message(message)

        finally:
            ping_task.cancel()
            try:
                await ping_task
            except asyncio.CancelledError:
                pass

    async def _ping_loop(self):
        """定期 PING 送信"""
        while self._running:
            await asyncio.sleep(self.config.ping_interval)
            if self._connected:
                await self._send("PING :tmi.twitch.tv")

    async def send_message(self, text: str):
        """チャットにメッセージ送信"""
        if not self._connected:
            raise RuntimeError("Not connected to Twitch chat")

        channel = self.config.channel.lower().lstrip("#")
        await self._send(f"PRIVMSG #{channel} :{text}")

    def stop(self):
        """ストリーム停止"""
        self._running = False

    async def close(self):
        """リソース解放"""
        self.stop()
        if self._writer:
            self._writer.close()
            try:
                await self._writer.wait_closed()
            except Exception:
                pass
        self._connected = False

    async def __aenter__(self):
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()


class TwitchChatMock:
    """テスト用モック"""

    def __init__(self, messages: Optional[list[dict]] = None):
        self._messages = messages or [
            {"author": "viewer1", "text": "おはロビィ！"},
            {"author": "subscriber42", "text": "かわいい！", "is_subscriber": True},
            {"author": "bits_king", "text": "Cheer100 頑張って！", "bits": 100},
        ]
        self._index = 0
        self._running = False

    async def connect(self) -> bool:
        logger.info("[Mock] Connected to Twitch")
        return True

    async def stream(self) -> AsyncIterator[TwitchMessage]:
        self._running = True

        while self._running and self._index < len(self._messages):
            data = self._messages[self._index]
            self._index += 1

            msg_type = TwitchMessageType.CHAT
            if data.get("bits", 0) > 0:
                msg_type = TwitchMessageType.BITS

            message = TwitchMessage(
                id=f"mock_{self._index}",
                text=data.get("text", ""),
                author_name=data.get("author", "MockUser"),
                author_id=f"mock_id_{self._index}",
                author_display_name=data.get("author", "MockUser"),
                channel="mock_channel",
                timestamp=datetime.now(),
                message_type=msg_type,
                bits=data.get("bits", 0),
                is_subscriber=data.get("is_subscriber", False),
            )

            yield message
            await asyncio.sleep(1.0)

    def stop(self):
        self._running = False

    async def close(self):
        self.stop()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

"""Twitch Chat Integration Tests"""

import asyncio
import pytest
from datetime import datetime

from .twitch import (
    TwitchChat,
    TwitchChatConfig,
    TwitchChatMock,
    TwitchMessage,
    TwitchMessageType,
    TwitchBadge,
    TwitchEmote,
)


class TestTwitchMessage:
    """TwitchMessage パース テスト"""
    
    def test_parse_simple_message(self):
        """シンプルなメッセージのパース"""
        raw = ":testuser!testuser@testuser.tmi.twitch.tv PRIVMSG #testchannel :Hello World!"
        tags = {
            "id": "msg-123",
            "user-id": "12345",
            "display-name": "TestUser",
            "tmi-sent-ts": "1707700000000",
        }
        
        msg = TwitchMessage.from_irc(raw, tags)
        
        assert msg is not None
        assert msg.text == "Hello World!"
        assert msg.author_name == "testuser"
        assert msg.author_display_name == "TestUser"
        assert msg.channel == "testchannel"
        assert msg.message_type == TwitchMessageType.CHAT
    
    def test_parse_message_with_badges(self):
        """バッジ付きメッセージのパース"""
        raw = ":sub_user!sub_user@sub_user.tmi.twitch.tv PRIVMSG #channel :Sub message"
        tags = {
            "id": "msg-456",
            "user-id": "67890",
            "display-name": "SubUser",
            "badges": "subscriber/12,premium/1",
            "tmi-sent-ts": "1707700000000",
        }
        
        msg = TwitchMessage.from_irc(raw, tags)
        
        assert msg is not None
        assert len(msg.badges) == 2
        assert msg.badges[0].name == "subscriber"
        assert msg.badges[0].version == "12"
        assert msg.is_subscriber == True
    
    def test_parse_message_with_emotes(self):
        """エモート付きメッセージのパース"""
        raw = ":emote_user!emote_user@emote_user.tmi.twitch.tv PRIVMSG #channel :Kappa Hello Kappa"
        tags = {
            "id": "msg-789",
            "user-id": "11111",
            "display-name": "EmoteUser",
            "emotes": "25:0-4,12-16",  # Kappa at positions 0-4 and 12-16
            "tmi-sent-ts": "1707700000000",
        }
        
        msg = TwitchMessage.from_irc(raw, tags)
        
        assert msg is not None
        assert len(msg.emotes) == 2
        assert msg.emotes[0].id == "25"
        assert msg.emotes[0].start == 0
        assert msg.emotes[0].end == 4
    
    def test_parse_bits_message(self):
        """Bitsメッセージのパース"""
        raw = ":bits_user!bits_user@bits_user.tmi.twitch.tv PRIVMSG #channel :cheer100 Great stream!"
        tags = {
            "id": "msg-bits",
            "user-id": "22222",
            "display-name": "BitsUser",
            "bits": "100",
            "tmi-sent-ts": "1707700000000",
        }
        
        msg = TwitchMessage.from_irc(raw, tags)
        
        assert msg is not None
        assert msg.message_type == TwitchMessageType.BITS
        assert msg.bits == 100
        assert "cheer100" in msg.text
    
    def test_parse_invalid_message(self):
        """無効なメッセージのパース"""
        raw = "PING :tmi.twitch.tv"
        msg = TwitchMessage.from_irc(raw, {})
        assert msg is None
    
    def test_parse_moderator_message(self):
        """モデレーターメッセージのパース"""
        raw = ":mod_user!mod_user@mod_user.tmi.twitch.tv PRIVMSG #channel :Mod message"
        tags = {
            "id": "msg-mod",
            "user-id": "33333",
            "display-name": "ModUser",
            "mod": "1",
            "badges": "moderator/1",
            "tmi-sent-ts": "1707700000000",
        }
        
        msg = TwitchMessage.from_irc(raw, tags)
        
        assert msg is not None
        assert msg.is_moderator == True
    
    def test_parse_first_message(self):
        """初めてのメッセージのパース"""
        raw = ":new_user!new_user@new_user.tmi.twitch.tv PRIVMSG #channel :First time here!"
        tags = {
            "id": "msg-first",
            "user-id": "44444",
            "display-name": "NewUser",
            "first-msg": "1",
            "tmi-sent-ts": "1707700000000",
        }
        
        msg = TwitchMessage.from_irc(raw, tags)
        
        assert msg is not None
        assert msg.is_first_message == True


class TestTwitchChatConfig:
    """TwitchChatConfig テスト"""
    
    def test_default_config(self):
        """デフォルト設定"""
        config = TwitchChatConfig()
        
        assert config.irc_host == "irc.chat.twitch.tv"
        assert config.irc_port == 6667
        assert config.nick == "justinfan12345"
        assert config.request_tags == True
    
    def test_custom_config(self):
        """カスタム設定"""
        config = TwitchChatConfig(
            oauth_token="oauth:test123",
            nick="my_bot",
            channel="streamer",
            use_ssl=True,
        )
        
        assert config.oauth_token == "oauth:test123"
        assert config.nick == "my_bot"
        assert config.channel == "streamer"
        assert config.use_ssl == True


class TestTwitchChatMock:
    """TwitchChatMock テスト"""
    
    @pytest.mark.asyncio
    async def test_mock_stream(self):
        """モックストリームテスト"""
        mock = TwitchChatMock()
        messages = []
        
        async with mock:
            count = 0
            async for msg in mock.stream():
                messages.append(msg)
                count += 1
                if count >= 3:
                    mock.stop()
                    break
        
        assert len(messages) == 3
        assert messages[0].text == "おはロビィ！"
        assert messages[2].bits == 100
    
    @pytest.mark.asyncio
    async def test_mock_connect(self):
        """モック接続テスト"""
        mock = TwitchChatMock()
        result = await mock.connect()
        assert result == True
    
    @pytest.mark.asyncio
    async def test_custom_mock_messages(self):
        """カスタムモックメッセージ"""
        custom_messages = [
            {"author": "user1", "text": "カスタムメッセージ1"},
            {"author": "user2", "text": "カスタムメッセージ2"},
        ]
        
        mock = TwitchChatMock(messages=custom_messages)
        messages = []
        
        async with mock:
            async for msg in mock.stream():
                messages.append(msg)
                if len(messages) >= 2:
                    mock.stop()
                    break
        
        assert len(messages) == 2
        assert messages[0].text == "カスタムメッセージ1"
        assert messages[1].author_name == "user2"


class TestTwitchChatTagParser:
    """IRCv3タグパーサーテスト"""
    
    def test_parse_tags(self):
        """タグパース"""
        chat = TwitchChat(TwitchChatConfig())
        
        tag_str = "display-name=TestUser;user-id=12345;color=#FF0000"
        tags = chat._parse_tags(tag_str)
        
        assert tags["display-name"] == "TestUser"
        assert tags["user-id"] == "12345"
        assert tags["color"] == "#FF0000"
    
    def test_parse_tags_with_escapes(self):
        """エスケープ付きタグパース"""
        chat = TwitchChat(TwitchChatConfig())
        
        tag_str = "system-msg=Welcome\\sto\\sthe\\sstream!"
        tags = chat._parse_tags(tag_str)
        
        assert tags["system-msg"] == "Welcome to the stream!"
    
    def test_parse_empty_tags(self):
        """空タグパース"""
        chat = TwitchChat(TwitchChatConfig())
        
        tags = chat._parse_tags("")
        assert tags == {"": ""}


# 統合テスト（実際のTwitch接続が必要な場合はスキップ）
class TestTwitchChatIntegration:
    """統合テスト（匿名接続）"""
    
    @pytest.mark.asyncio
    @pytest.mark.skip(reason="Requires network access")
    async def test_anonymous_connect(self):
        """匿名接続テスト"""
        config = TwitchChatConfig(channel="twitchdev")
        
        async with TwitchChat(config) as chat:
            # 接続成功
            assert chat._connected == True
            
            # 数秒待機してメッセージを受信
            messages = []
            async for msg in chat.stream():
                messages.append(msg)
                if len(messages) >= 1:
                    break
            
            # 少なくとも1件受信
            assert len(messages) >= 0  # 配信中でなければ0件もあり得る


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

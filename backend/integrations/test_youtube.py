"""YouTube Integration Tests"""

import asyncio

import pytest

from .youtube import (
    CommentType,
    YouTubeChat,
    YouTubeChatConfig,
    YouTubeChatMock,
    YouTubeComment,
)


class TestYouTubeComment:
    """YouTubeCommentのテスト"""

    def test_from_api_response_text_message(self):
        """通常テキストメッセージのパース"""
        item = {
            "id": "test123",
            "snippet": {
                "publishedAt": "2026-02-12T00:00:00Z",
                "textMessageDetails": {
                    "messageText": "おはロビィ！"
                }
            },
            "authorDetails": {
                "displayName": "テストユーザー",
                "channelId": "UC_TEST",
                "profileImageUrl": "https://example.com/avatar.jpg"
            }
        }

        comment = YouTubeComment.from_api_response(item)

        assert comment.id == "test123"
        assert comment.text == "おはロビィ！"
        assert comment.author_name == "テストユーザー"
        assert comment.author_channel_id == "UC_TEST"
        assert comment.comment_type == CommentType.TEXT
        assert comment.amount is None

    def test_from_api_response_super_chat(self):
        """Super Chatのパース"""
        item = {
            "id": "superchat123",
            "snippet": {
                "publishedAt": "2026-02-12T00:00:00Z",
                "superChatDetails": {
                    "userComment": "頑張って！",
                    "amountMicros": "500000000",  # 500円
                    "currency": "JPY"
                }
            },
            "authorDetails": {
                "displayName": "太っ腹さん",
                "channelId": "UC_RICH",
                "profileImageUrl": ""
            }
        }

        comment = YouTubeComment.from_api_response(item)

        assert comment.comment_type == CommentType.SUPER_CHAT
        assert comment.text == "頑張って！"
        assert comment.amount == 500.0
        assert comment.currency == "JPY"


class TestYouTubeChat:
    """YouTubeChatクライアントのテスト"""

    def test_extract_video_id_from_id(self):
        """動画IDの直接指定"""
        config = YouTubeChatConfig(api_key="dummy")
        chat = YouTubeChat(config)

        assert chat._extract_video_id("dQw4w9WgXcQ") == "dQw4w9WgXcQ"

    def test_extract_video_id_from_watch_url(self):
        """watch URLからの抽出"""
        config = YouTubeChatConfig(api_key="dummy")
        chat = YouTubeChat(config)

        url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        assert chat._extract_video_id(url) == "dQw4w9WgXcQ"

    def test_extract_video_id_from_short_url(self):
        """短縮URLからの抽出"""
        config = YouTubeChatConfig(api_key="dummy")
        chat = YouTubeChat(config)

        url = "https://youtu.be/dQw4w9WgXcQ"
        assert chat._extract_video_id(url) == "dQw4w9WgXcQ"

    def test_extract_video_id_from_live_url(self):
        """ライブURLからの抽出"""
        config = YouTubeChatConfig(api_key="dummy")
        chat = YouTubeChat(config)

        url = "https://www.youtube.com/live/dQw4w9WgXcQ"
        assert chat._extract_video_id(url) == "dQw4w9WgXcQ"


class TestYouTubeChatMock:
    """モッククライアントのテスト"""

    @pytest.mark.asyncio
    async def test_mock_stream(self):
        """モックストリームのテスト"""
        comments_data = [
            {"author": "ユーザー1", "text": "こんにちは"},
            {"author": "ユーザー2", "text": "かわいい！"},
        ]

        mock = YouTubeChatMock(comments_data)
        await mock.connect("dummy_video")

        received = []
        async for comment in mock.stream():
            received.append(comment)
            if len(received) >= 2:
                mock.stop()

        assert len(received) == 2
        assert received[0].text == "こんにちは"
        assert received[1].author_name == "ユーザー2"


if __name__ == "__main__":
    # 簡易テスト実行

    # 同期テスト
    test_comment = TestYouTubeComment()
    test_comment.test_from_api_response_text_message()
    test_comment.test_from_api_response_super_chat()
    print("✅ YouTubeComment tests passed")

    test_chat = TestYouTubeChat()
    test_chat.test_extract_video_id_from_id()
    test_chat.test_extract_video_id_from_watch_url()
    test_chat.test_extract_video_id_from_short_url()
    test_chat.test_extract_video_id_from_live_url()
    print("✅ YouTubeChat URL parsing tests passed")

    # 非同期テスト
    async def run_async_tests():
        test_mock = TestYouTubeChatMock()
        await test_mock.test_mock_stream()
        print("✅ YouTubeChatMock stream test passed")

    asyncio.run(run_async_tests())

    print("\n✅ All YouTube integration tests passed!")

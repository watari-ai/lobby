"""Phase 3 統合テスト - リアルタイム応答パイプライン

LiveMode のエンドツーエンドテスト:
- OpenClaw Gateway 連携
- 感情分析 → TTS → Live2D パラメータ生成
- WebSocket API
- OBS連携
"""

import asyncio
import json
from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestLiveModeIntegration:
    """LiveMode 統合テスト"""
    
    @pytest.fixture
    def live_imports(self):
        """LiveMode関連のインポート（循環参照回避）"""
        from backend.modes.live import (
            LiveMode,
            LiveModeConfig,
            LiveInput,
            LiveOutput,
            InputSource,
            YouTubeLiveMode,
            create_lobby_live_mode,
        )
        from backend.core.openclaw import OpenClawConfig
        from backend.core.tts import TTSConfig
        from backend.core.emotion import Emotion
        
        return {
            "LiveMode": LiveMode,
            "LiveModeConfig": LiveModeConfig,
            "LiveInput": LiveInput,
            "LiveOutput": LiveOutput,
            "InputSource": InputSource,
            "YouTubeLiveMode": YouTubeLiveMode,
            "create_lobby_live_mode": create_lobby_live_mode,
            "OpenClawConfig": OpenClawConfig,
            "TTSConfig": TTSConfig,
            "Emotion": Emotion,
        }
    
    @pytest.fixture
    def mock_config(self, tmp_path, live_imports):
        """テスト用設定"""
        LiveModeConfig = live_imports["LiveModeConfig"]
        OpenClawConfig = live_imports["OpenClawConfig"]
        TTSConfig = live_imports["TTSConfig"]
        
        return LiveModeConfig(
            openclaw=OpenClawConfig(
                base_url="http://localhost:18789",
                system_prompt="テスト用プロンプト",
            ),
            tts=TTSConfig(
                base_url="http://localhost:8001",
                voice="lobby",
            ),
            audio_output_dir=tmp_path / "audio",
            generate_live2d=False,
        )
    
    @pytest.fixture
    def sample_input(self, live_imports):
        """テスト用入力"""
        LiveInput = live_imports["LiveInput"]
        InputSource = live_imports["InputSource"]
        
        return LiveInput(
            text="こんにちは！元気ですか？",
            source=InputSource.MANUAL,
            author="TestUser",
            timestamp=datetime.now(),
        )
    
    def test_input_filtering(self, mock_config, live_imports):
        """入力フィルタリングテスト"""
        LiveMode = live_imports["LiveMode"]
        LiveInput = live_imports["LiveInput"]
        InputSource = live_imports["InputSource"]
        
        mock_config.min_input_length = 3
        mock_config.max_input_length = 100
        mock_config.blocked_words = ["NG", "禁止"]
        
        live = LiveMode(mock_config)
        
        # 短すぎる
        short_input = LiveInput(text="あ", source=InputSource.MANUAL, author="User")
        assert live.add_input(short_input) is False
        
        # 長すぎる
        long_input = LiveInput(text="あ" * 150, source=InputSource.MANUAL, author="User")
        assert live.add_input(long_input) is False
        
        # NGワード
        ng_input = LiveInput(text="これはNGワードです", source=InputSource.MANUAL, author="User")
        assert live.add_input(ng_input) is False
        
        # 正常
        ok_input = LiveInput(text="これは正常な入力です", source=InputSource.MANUAL, author="User")
        assert live.add_input(ok_input) is True
        assert live.queue_size == 1
    
    @pytest.mark.asyncio
    async def test_queue_processing(self, mock_config, live_imports):
        """キュー処理テスト"""
        LiveMode = live_imports["LiveMode"]
        LiveInput = live_imports["LiveInput"]
        InputSource = live_imports["InputSource"]
        
        with patch.object(LiveMode, '_process_input', new_callable=AsyncMock) as mock_process:
            live = LiveMode(mock_config)
            
            # 入力追加
            for i in range(5):
                live.add_input(LiveInput(
                    text=f"メッセージ {i}",
                    source=InputSource.MANUAL,
                    author="User",
                ))
            
            assert live.queue_size == 5
            
            # 処理開始
            await live.start()
            await asyncio.sleep(0.3)
            await live.stop()
            
            # 処理されたか確認
            assert mock_process.call_count == 5
    
    @pytest.mark.asyncio
    async def test_start_stop_lifecycle(self, mock_config, live_imports):
        """ライフサイクルテスト"""
        LiveMode = live_imports["LiveMode"]
        
        live = LiveMode(mock_config)
        
        assert live.is_running is False
        
        await live.start()
        assert live.is_running is True
        
        await live.stop()
        assert live.is_running is False


class TestYouTubeLiveModeIntegration:
    """YouTubeLiveMode 統合テスト"""
    
    @pytest.fixture
    def live_imports(self):
        """インポート"""
        from backend.modes.live import (
            LiveModeConfig,
            LiveInput,
            InputSource,
            YouTubeLiveMode,
        )
        from backend.core.openclaw import OpenClawConfig
        from backend.core.tts import TTSConfig
        
        return {
            "LiveModeConfig": LiveModeConfig,
            "LiveInput": LiveInput,
            "InputSource": InputSource,
            "YouTubeLiveMode": YouTubeLiveMode,
            "OpenClawConfig": OpenClawConfig,
            "TTSConfig": TTSConfig,
        }
    
    @pytest.fixture
    def youtube_config(self, tmp_path, live_imports):
        """YouTube用設定"""
        LiveModeConfig = live_imports["LiveModeConfig"]
        OpenClawConfig = live_imports["OpenClawConfig"]
        TTSConfig = live_imports["TTSConfig"]
        
        return LiveModeConfig(
            openclaw=OpenClawConfig(base_url="http://localhost:18789"),
            tts=TTSConfig(base_url="http://localhost:8001"),
            audio_output_dir=tmp_path / "audio",
            generate_live2d=False,
        )
    
    @pytest.mark.asyncio
    async def test_priority_queue(self, youtube_config, live_imports):
        """スパチャ優先キューテスト"""
        YouTubeLiveMode = live_imports["YouTubeLiveMode"]
        LiveInput = live_imports["LiveInput"]
        InputSource = live_imports["InputSource"]
        
        live = YouTubeLiveMode(youtube_config)
        
        # 通常コメントを先に追加
        for i in range(3):
            live.add_input(LiveInput(
                text=f"通常コメント {i}",
                source=InputSource.YOUTUBE_COMMENT,
                author=f"User{i}",
            ))
        
        # スパチャを追加（優先キューへ）
        live._priority_queue.append(LiveInput(
            text="スパチャコメント！",
            source=InputSource.YOUTUBE_COMMENT,
            author="SuperChatUser",
            metadata={"amount": 1000, "currency": "JPY"},
        ))
        
        assert live.queue_size == 3
        assert len(live._priority_queue) == 1


class TestWebSocketAPIIntegration:
    """WebSocket API 統合テスト"""
    
    @pytest.mark.asyncio
    async def test_websocket_connection(self):
        """WebSocket接続テスト（モック）"""
        from backend.api.websocket import ConnectionManager
        
        manager = ConnectionManager()
        
        # モックWebSocket
        mock_ws = AsyncMock()
        mock_ws.accept = AsyncMock()
        mock_ws.send_json = AsyncMock()
        mock_ws.receive_json = AsyncMock(return_value={"type": "ping"})
        
        # 接続（async）
        await manager.connect(mock_ws)
        assert len(manager.active_connections) == 1
        
        # 切断（WebSocketオブジェクトを直接渡す）
        manager.disconnect(mock_ws)
        assert len(manager.active_connections) == 0
    
    @pytest.mark.asyncio
    async def test_broadcast_parameters(self):
        """パラメータブロードキャストテスト"""
        from backend.api.websocket import ConnectionManager
        from backend.core.live2d import Live2DParameters
        
        manager = ConnectionManager()
        
        # 複数接続
        mock_ws1 = AsyncMock()
        mock_ws1.accept = AsyncMock()
        mock_ws1.send_json = AsyncMock()
        mock_ws2 = AsyncMock()
        mock_ws2.accept = AsyncMock()
        mock_ws2.send_json = AsyncMock()
        
        await manager.connect(mock_ws1)
        await manager.connect(mock_ws2)
        
        # ブロードキャスト（Live2DParametersオブジェクトを使用）
        params = Live2DParameters(
            param_mouth_open_y=0.5,
            param_eye_l_open=1.0,
            param_eye_r_open=1.0,
        )
        await manager.broadcast_parameters(params)
        
        # 両方に送信されたか（初回接続時の送信 + ブロードキャスト）
        assert mock_ws1.send_json.call_count >= 1
        assert mock_ws2.send_json.call_count >= 1


class TestOBSIntegration:
    """OBS WebSocket 統合テスト（モック）"""
    
    def test_obs_config(self):
        """OBS設定テスト"""
        from backend.integrations.obs import OBSConfig
        
        config = OBSConfig(
            host="localhost",
            port=4455,
            password="test_password",
        )
        
        assert config.host == "localhost"
        assert config.port == 4455
    
    @pytest.mark.asyncio
    async def test_obs_client_initialization(self):
        """OBSクライアント初期化テスト"""
        from backend.integrations.obs import OBSWebSocketClient, OBSConfig
        
        config = OBSConfig()
        client = OBSWebSocketClient(config)
        
        assert client.config.host == "localhost"
        assert client._connected is False


class TestLobbyCharacterIntegration:
    """ロビィキャラクター専用テスト"""
    
    def test_lobby_system_prompt(self):
        """ロビィのシステムプロンプトテスト"""
        from backend.core.openclaw import LOBBY_SYSTEM_PROMPT
        
        # プロンプトが存在し、空でないこと
        assert LOBBY_SYSTEM_PROMPT is not None
        assert len(LOBBY_SYSTEM_PROMPT) > 0
    
    @pytest.mark.asyncio
    async def test_create_lobby_live_mode(self):
        """ロビィ用ライブモード生成テスト"""
        from backend.modes.live import create_lobby_live_mode
        
        with patch('backend.core.openclaw.OpenClawClient'):
            with patch('backend.core.tts.TTSClient'):
                live = await create_lobby_live_mode(
                    gateway_url="http://localhost:18790",
                    tts_url="http://localhost:8001",
                )
                assert live is not None
                assert live.config.tts.voice == "lobby"


class TestEndToEndPipeline:
    """エンドツーエンドパイプラインテスト"""
    
    @pytest.mark.asyncio
    async def test_emotion_analysis_in_pipeline(self):
        """パイプライン内の感情分析テスト"""
        from backend.core.emotion import EmotionAnalyzer, Emotion
        
        analyzer = EmotionAnalyzer()
        
        # ハッピーな応答（明確なハッピーキーワード）
        happy_result = analyzer.analyze("嬉しい♪楽しいね！")
        assert happy_result.primary == Emotion.HAPPY
        
        # 興奮した応答（ロビィっぽい口調）
        excited_result = analyzer.analyze("マジっすか！！やばいっすね！！")
        assert excited_result.primary == Emotion.EXCITED
        
        # 悲しい応答
        sad_result = analyzer.analyze("悲しい...泣きそう...")
        assert sad_result.primary == Emotion.SAD
        
        # タグ指定（明示的な感情指定）
        tagged_result = analyzer.analyze("[angry] 許さないぞ！")
        assert tagged_result.primary == Emotion.ANGRY


# pytest実行用設定
if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])

"""Tests for TTS (Text-to-Speech) Client"""

import base64
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from backend.core.tts import DEFAULT_CONFIG, TTSClient, TTSConfig


class TestTTSConfig:
    """TTSConfig tests"""

    def test_default_config(self):
        config = TTSConfig()
        assert config.provider == "miotts"
        assert config.base_url == "http://localhost:8001"
        assert config.voice == "lobby"
        assert config.api_key == "not-needed"
        assert config.response_format == "base64"

    def test_custom_config(self):
        config = TTSConfig(
            provider="openai",
            base_url="http://localhost:8880",
            voice="Vivian",
            model="qwen3-tts",
        )
        assert config.provider == "openai"
        assert config.voice == "Vivian"
        assert config.model == "qwen3-tts"

    def test_default_emotion_prompts(self):
        config = TTSConfig()
        assert "happy" in config.emotion_prompts
        assert "sad" in config.emotion_prompts
        assert "neutral" in config.emotion_prompts
        assert config.emotion_prompts["neutral"] == ""

    def test_custom_emotion_prompts(self):
        custom = {"happy": "joyful", "sad": "gloomy"}
        config = TTSConfig(emotion_prompts=custom)
        assert config.emotion_prompts == custom

    def test_default_config_constant(self):
        assert DEFAULT_CONFIG.provider == "miotts"
        assert DEFAULT_CONFIG.voice == "lobby"


class TestTTSClientInit:
    """TTSClient initialization tests"""

    def test_default_init(self):
        client = TTSClient()
        assert client.config.provider == "miotts"

    def test_custom_config_init(self):
        config = TTSConfig(provider="openai")
        client = TTSClient(config)
        assert client.config.provider == "openai"


class TestTTSClientMioTTS:
    """TTSClient MioTTS provider tests"""

    @pytest.fixture
    def client(self):
        return TTSClient(TTSConfig(provider="miotts"))

    @pytest.mark.asyncio
    async def test_synthesize_miotts_success(self, client):
        audio_bytes = b"fake-audio-data"
        audio_b64 = base64.b64encode(audio_bytes).decode()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"audio": audio_b64}
        mock_response.raise_for_status = MagicMock()

        with patch.object(client._client, "post", new_callable=AsyncMock, return_value=mock_response) as mock_post:
            result = await client.synthesize("テスト")
            assert result == audio_bytes
            mock_post.assert_called_once()
            call_kwargs = mock_post.call_args
            payload = call_kwargs.kwargs.get("json") or call_kwargs[1].get("json")
            assert payload["text"] == "テスト"
            assert payload["reference"]["preset_id"] == "lobby"

    @pytest.mark.asyncio
    async def test_synthesize_miotts_unexpected_response(self, client):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"error": "no audio"}
        mock_response.raise_for_status = MagicMock()

        with patch.object(client._client, "post", new_callable=AsyncMock, return_value=mock_response):
            with pytest.raises(ValueError, match="Unexpected MioTTS response"):
                await client.synthesize("テスト")

    @pytest.mark.asyncio
    async def test_synthesize_miotts_http_error(self, client):
        with patch.object(
            client._client, "post", side_effect=httpx.HTTPError("Connection refused")
        ):
            with pytest.raises(httpx.HTTPError):
                await client.synthesize("テスト")

    @pytest.mark.asyncio
    async def test_synthesize_with_output_path(self, client, tmp_path):
        audio_bytes = b"fake-audio-data"
        audio_b64 = base64.b64encode(audio_bytes).decode()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"audio": audio_b64}
        mock_response.raise_for_status = MagicMock()

        output = tmp_path / "subdir" / "output.wav"

        with patch.object(client._client, "post", return_value=mock_response):
            result = await client.synthesize("テスト", output_path=output)
            assert result == audio_bytes
            assert output.exists()
            assert output.read_bytes() == audio_bytes


class TestTTSClientOpenAI:
    """TTSClient OpenAI-compatible provider tests"""

    @pytest.fixture
    def client(self):
        return TTSClient(
            TTSConfig(
                provider="openai",
                base_url="http://localhost:8880",
                voice="Vivian",
                model="qwen3-tts",
                api_key="test-key",
                response_format="mp3",
            )
        )

    @pytest.mark.asyncio
    async def test_synthesize_openai_success(self, client):
        audio_bytes = b"fake-mp3-data"
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = audio_bytes
        mock_response.raise_for_status = MagicMock()

        with patch.object(client._client, "post", return_value=mock_response) as mock_post:
            result = await client.synthesize("Hello")
            assert result == audio_bytes
            call_kwargs = mock_post.call_args
            payload = call_kwargs.kwargs.get("json") or call_kwargs[1].get("json")
            assert payload["voice"] == "Vivian"
            assert payload["model"] == "qwen3-tts"
            assert payload["input"] == "Hello"
            headers = call_kwargs.kwargs.get("headers") or call_kwargs[1].get("headers")
            assert "Bearer test-key" in headers["Authorization"]

    @pytest.mark.asyncio
    async def test_synthesize_openai_with_emotion(self, client):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b"audio"
        mock_response.raise_for_status = MagicMock()

        with patch.object(client._client, "post", return_value=mock_response) as mock_post:
            await client.synthesize("やったー", emotion="happy")
            call_kwargs = mock_post.call_args
            payload = call_kwargs.kwargs.get("json") or call_kwargs[1].get("json")
            # Should prepend emotion prompt
            assert payload["input"].startswith("[明るく楽しそうに]")
            assert "やったー" in payload["input"]

    @pytest.mark.asyncio
    async def test_synthesize_openai_neutral_no_prefix(self, client):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b"audio"
        mock_response.raise_for_status = MagicMock()

        with patch.object(client._client, "post", return_value=mock_response) as mock_post:
            await client.synthesize("普通の声", emotion="neutral")
            call_kwargs = mock_post.call_args
            payload = call_kwargs.kwargs.get("json") or call_kwargs[1].get("json")
            assert payload["input"] == "普通の声"

    @pytest.mark.asyncio
    async def test_synthesize_openai_http_error(self, client):
        with patch.object(
            client._client, "post", side_effect=httpx.HTTPError("Server error")
        ):
            with pytest.raises(httpx.HTTPError):
                await client.synthesize("テスト")

    @pytest.mark.asyncio
    async def test_synthesize_openai_default_model(self):
        client = TTSClient(TTSConfig(provider="openai", model=""))
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b"audio"
        mock_response.raise_for_status = MagicMock()

        with patch.object(client._client, "post", return_value=mock_response) as mock_post:
            await client.synthesize("test")
            call_kwargs = mock_post.call_args
            payload = call_kwargs.kwargs.get("json") or call_kwargs[1].get("json")
            assert payload["model"] == "tts-1"


class TestTTSClientHealthAndPresets:
    """Health check and preset listing tests"""

    @pytest.mark.asyncio
    async def test_check_health_miotts_success(self):
        client = TTSClient(TTSConfig(provider="miotts"))
        mock_response = MagicMock()
        mock_response.status_code = 200

        with patch.object(client._client, "get", return_value=mock_response):
            assert await client.check_health() is True

    @pytest.mark.asyncio
    async def test_check_health_miotts_failure(self):
        client = TTSClient(TTSConfig(provider="miotts"))

        with patch.object(client._client, "get", side_effect=Exception("down")):
            assert await client.check_health() is False

    @pytest.mark.asyncio
    async def test_check_health_openai_success(self):
        client = TTSClient(TTSConfig(provider="openai"))
        mock_response = MagicMock()
        mock_response.status_code = 200

        with patch.object(client._client, "get", return_value=mock_response) as mock_get:
            assert await client.check_health() is True
            # Should check /v1/models for openai provider
            mock_get.assert_called_once()
            call_url = mock_get.call_args[0][0]
            assert "/v1/models" in call_url

    @pytest.mark.asyncio
    async def test_check_health_non_200(self):
        client = TTSClient(TTSConfig(provider="miotts"))
        mock_response = MagicMock()
        mock_response.status_code = 503

        with patch.object(client._client, "get", return_value=mock_response):
            assert await client.check_health() is False

    @pytest.mark.asyncio
    async def test_list_presets_miotts(self):
        client = TTSClient(TTSConfig(provider="miotts"))
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"presets": ["lobby", "narrator"]}
        mock_response.raise_for_status = MagicMock()

        with patch.object(client._client, "get", return_value=mock_response):
            presets = await client.list_presets()
            assert presets == ["lobby", "narrator"]

    @pytest.mark.asyncio
    async def test_list_presets_openai_returns_empty(self):
        client = TTSClient(TTSConfig(provider="openai"))
        presets = await client.list_presets()
        assert presets == []

    @pytest.mark.asyncio
    async def test_list_presets_error_returns_empty(self):
        client = TTSClient(TTSConfig(provider="miotts"))

        with patch.object(client._client, "get", side_effect=Exception("error")):
            presets = await client.list_presets()
            assert presets == []


class TestTTSClientLifecycle:
    """Context manager and close tests"""

    @pytest.mark.asyncio
    async def test_close(self):
        client = TTSClient()
        with patch.object(client._client, "aclose", new_callable=AsyncMock) as mock_close:
            await client.close()
            mock_close.assert_called_once()

    @pytest.mark.asyncio
    async def test_async_context_manager(self):
        async with TTSClient() as client:
            assert client is not None
            assert isinstance(client, TTSClient)

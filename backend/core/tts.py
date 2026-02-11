"""TTS (Text-to-Speech) Client - Qwen3-TTS, MioTTS & OpenAI Compatible APIs"""

from dataclasses import dataclass
from pathlib import Path
from typing import Optional
import base64

import httpx
from loguru import logger


@dataclass
class TTSConfig:
    """TTS設定"""
    provider: str = "miotts"  # "qwen3-tts", "miotts", or "openai"
    base_url: str = "http://localhost:8001"
    voice: str = "lobby"  # MioTTS preset_id or OpenAI voice
    api_key: str = "not-needed"
    model: str = ""
    response_format: str = "base64"  # MioTTS: "wav" or "base64" (base64 returns JSON)

    # 感情マッピング
    emotion_prompts: dict[str, str] | None = None

    def __post_init__(self):
        if self.emotion_prompts is None:
            self.emotion_prompts = {
                "happy": "明るく楽しそうに",
                "sad": "しんみりと悲しげに",
                "excited": "テンション高く興奮して",
                "angry": "怒った声で",
                "surprised": "驚いた声で",
                "neutral": "",
            }


class TTSClient:
    """マルチプロバイダーTTS APIクライアント"""

    def __init__(self, config: TTSConfig | None = None):
        self.config = config or TTSConfig()
        self._client = httpx.AsyncClient(timeout=120.0)

    async def synthesize(
        self,
        text: str,
        emotion: str = "neutral",
        output_path: Optional[Path] = None,
    ) -> bytes:
        """テキストを音声に変換

        Args:
            text: 変換するテキスト
            emotion: 感情タグ（happy, sad, excited, angry, surprised, neutral）
            output_path: 出力ファイルパス（指定時はファイルにも保存）

        Returns:
            音声データ（bytes）
        """
        if self.config.provider == "miotts":
            audio_data = await self._synthesize_miotts(text, emotion)
        else:
            audio_data = await self._synthesize_openai(text, emotion)

        if output_path:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(audio_data)
            logger.info(f"Audio saved: {output_path}")

        return audio_data

    async def _synthesize_miotts(self, text: str, emotion: str) -> bytes:
        """MioTTS APIで音声合成"""
        url = f"{self.config.base_url}/v1/tts"

        payload = {
            "text": text,
            "reference": {
                "type": "preset",
                "preset_id": self.config.voice,
            },
            "output": {
                "format": self.config.response_format,
            },
        }

        logger.debug(f"MioTTS request: {text[:50]}... (preset: {self.config.voice})")

        try:
            response = await self._client.post(url, json=payload)
            response.raise_for_status()
            result = response.json()

            # MioTTSはbase64でオーディオを返す
            if "audio" in result:
                audio_b64 = result["audio"]
                return base64.b64decode(audio_b64)
            else:
                raise ValueError(f"Unexpected MioTTS response: {result}")

        except httpx.HTTPError as e:
            logger.error(f"MioTTS error: {e}")
            raise

    async def _synthesize_openai(self, text: str, emotion: str) -> bytes:
        """OpenAI互換APIで音声合成（Qwen3-TTS等）"""
        # 感情プロンプトを適用
        emotion_prompt = self.config.emotion_prompts.get(emotion, "")
        if emotion_prompt:
            full_text = f"[{emotion_prompt}]{text}"
        else:
            full_text = text

        url = f"{self.config.base_url}/v1/audio/speech"

        payload = {
            "model": self.config.model or "tts-1",
            "voice": self.config.voice,
            "input": full_text,
            "response_format": self.config.response_format,
        }

        headers = {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json",
        }

        logger.debug(f"OpenAI TTS request: {text[:50]}... (emotion: {emotion})")

        try:
            response = await self._client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            return response.content

        except httpx.HTTPError as e:
            logger.error(f"OpenAI TTS error: {e}")
            raise

    async def check_health(self) -> bool:
        """TTSサーバーの状態を確認"""
        try:
            if self.config.provider == "miotts":
                response = await self._client.get(f"{self.config.base_url}/health")
            else:
                response = await self._client.get(f"{self.config.base_url}/v1/models")
            return response.status_code == 200
        except Exception:
            return False

    async def list_presets(self) -> list[str]:
        """MioTTSプリセット一覧を取得"""
        if self.config.provider != "miotts":
            return []
        try:
            response = await self._client.get(f"{self.config.base_url}/v1/presets")
            response.raise_for_status()
            return response.json().get("presets", [])
        except Exception:
            return []

    async def close(self):
        """クライアントを閉じる"""
        await self._client.aclose()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()


# デフォルト設定（MioTTS + lobbyプリセット）
DEFAULT_CONFIG = TTSConfig(
    provider="miotts",
    base_url="http://localhost:8001",
    voice="lobby",
)

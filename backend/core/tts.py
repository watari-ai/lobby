"""TTS (Text-to-Speech) Client - Qwen3-TTS & OpenAI Compatible APIs"""

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import httpx
from loguru import logger


@dataclass
class TTSConfig:
    """TTS設定"""
    provider: str = "qwen3-tts"
    base_url: str = "http://localhost:8880/v1"
    voice: str = "Vivian"
    api_key: str = "not-needed"
    model: str = "qwen3-tts"
    response_format: str = "mp3"

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
    """OpenAI互換TTS APIクライアント"""

    def __init__(self, config: TTSConfig | None = None):
        self.config = config or TTSConfig()
        self._client = httpx.AsyncClient(timeout=60.0)

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
        # 感情プロンプトを適用
        emotion_prompt = self.config.emotion_prompts.get(emotion, "")
        if emotion_prompt:
            # Qwen3-TTSは指示をテキストの前に追加できる
            full_text = f"[{emotion_prompt}]{text}"
        else:
            full_text = text

        url = f"{self.config.base_url}/audio/speech"

        payload = {
            "model": self.config.model,
            "voice": self.config.voice,
            "input": full_text,
            "response_format": self.config.response_format,
        }

        headers = {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json",
        }

        logger.debug(f"TTS request: {text[:50]}... (emotion: {emotion})")

        try:
            response = await self._client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            audio_data = response.content

            if output_path:
                output_path.parent.mkdir(parents=True, exist_ok=True)
                output_path.write_bytes(audio_data)
                logger.info(f"Audio saved: {output_path}")

            return audio_data

        except httpx.HTTPError as e:
            logger.error(f"TTS error: {e}")
            raise

    async def check_health(self) -> bool:
        """TTSサーバーの状態を確認"""
        try:
            # OpenAI互換APIはmodelsエンドポイントを持つことが多い
            response = await self._client.get(f"{self.config.base_url}/models")
            return response.status_code == 200
        except Exception:
            return False

    async def close(self):
        """クライアントを閉じる"""
        await self._client.aclose()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

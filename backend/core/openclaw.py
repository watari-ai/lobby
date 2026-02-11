"""OpenClaw Gateway Client - AI応答生成連携"""

from dataclasses import dataclass, field
from typing import AsyncIterator, Optional
import asyncio

import httpx
from loguru import logger


@dataclass
class OpenClawConfig:
    """OpenClaw Gateway設定"""
    base_url: str = "http://localhost:18789"
    api_key: str = ""  # Gateway認証用（オプション）
    model: str = ""  # 空文字=Gatewayデフォルト
    timeout: float = 60.0
    max_tokens: int = 500
    temperature: float = 0.8
    system_prompt: str = ""
    
    # ストリーミング設定
    stream: bool = True


@dataclass
class Message:
    """チャットメッセージ"""
    role: str  # "user", "assistant", "system"
    content: str


@dataclass 
class CompletionResult:
    """AI応答結果"""
    text: str
    finish_reason: Optional[str] = None
    usage: dict = field(default_factory=dict)


class OpenClawClient:
    """OpenClaw Gateway連携クライアント
    
    OpenClawのchatCompletions APIを使ってAI応答を生成。
    ライブモードでコメントやマイク入力に対して応答を得る。
    """
    
    def __init__(self, config: Optional[OpenClawConfig] = None):
        self.config = config or OpenClawConfig()
        self._client: Optional[httpx.AsyncClient] = None
        self._conversation: list[Message] = []
        
    async def _get_client(self) -> httpx.AsyncClient:
        """HTTPクライアント取得（遅延初期化）"""
        if self._client is None:
            headers = {"Content-Type": "application/json"}
            if self.config.api_key:
                headers["Authorization"] = f"Bearer {self.config.api_key}"
            
            self._client = httpx.AsyncClient(
                base_url=self.config.base_url,
                headers=headers,
                timeout=httpx.Timeout(self.config.timeout),
            )
        return self._client
    
    def set_system_prompt(self, prompt: str):
        """システムプロンプト設定（キャラクター設定など）"""
        self.config.system_prompt = prompt
        self._conversation = []  # 会話リセット
        logger.info(f"System prompt set ({len(prompt)} chars)")
        
    def clear_conversation(self):
        """会話履歴クリア"""
        self._conversation = []
        logger.info("Conversation cleared")
    
    def _build_messages(self, user_input: str) -> list[dict]:
        """API用メッセージリスト構築"""
        messages = []
        
        # システムプロンプト
        if self.config.system_prompt:
            messages.append({
                "role": "system",
                "content": self.config.system_prompt,
            })
        
        # 会話履歴
        for msg in self._conversation:
            messages.append({
                "role": msg.role,
                "content": msg.content,
            })
        
        # 新しいユーザー入力
        messages.append({
            "role": "user",
            "content": user_input,
        })
        
        return messages
    
    async def chat(self, user_input: str) -> CompletionResult:
        """AI応答を生成（非ストリーミング）
        
        Args:
            user_input: ユーザー入力（コメント、マイク入力など）
            
        Returns:
            CompletionResult
        """
        client = await self._get_client()
        messages = self._build_messages(user_input)
        
        payload = {
            "messages": messages,
            "stream": False,
            "max_tokens": self.config.max_tokens,
            "temperature": self.config.temperature,
        }
        if self.config.model:
            payload["model"] = self.config.model
        
        logger.debug(f"OpenClaw request: {user_input[:50]}...")
        
        try:
            response = await client.post("/v1/chat/completions", json=payload)
            response.raise_for_status()
            data = response.json()
            
            # 応答を抽出
            choice = data.get("choices", [{}])[0]
            text = choice.get("message", {}).get("content", "")
            finish_reason = choice.get("finish_reason")
            usage = data.get("usage", {})
            
            # 会話履歴に追加
            self._conversation.append(Message(role="user", content=user_input))
            self._conversation.append(Message(role="assistant", content=text))
            
            # 履歴が長くなりすぎたら古いものを削除
            max_history = 20
            if len(self._conversation) > max_history * 2:
                self._conversation = self._conversation[-(max_history * 2):]
            
            logger.info(f"OpenClaw response: {text[:50]}...")
            
            return CompletionResult(
                text=text,
                finish_reason=finish_reason,
                usage=usage,
            )
            
        except httpx.HTTPStatusError as e:
            logger.error(f"OpenClaw API error: {e.response.status_code}")
            raise
        except Exception as e:
            logger.error(f"OpenClaw request failed: {e}")
            raise
    
    async def chat_stream(self, user_input: str) -> AsyncIterator[str]:
        """AI応答を生成（ストリーミング）
        
        Args:
            user_input: ユーザー入力
            
        Yields:
            テキストチャンク
        """
        client = await self._get_client()
        messages = self._build_messages(user_input)
        
        payload = {
            "messages": messages,
            "stream": True,
            "max_tokens": self.config.max_tokens,
            "temperature": self.config.temperature,
        }
        if self.config.model:
            payload["model"] = self.config.model
        
        logger.debug(f"OpenClaw stream request: {user_input[:50]}...")
        
        full_response = ""
        
        try:
            async with client.stream(
                "POST",
                "/v1/chat/completions",
                json=payload,
            ) as response:
                response.raise_for_status()
                
                async for line in response.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    
                    data_str = line[6:]  # "data: " を除去
                    if data_str == "[DONE]":
                        break
                    
                    try:
                        import json
                        data = json.loads(data_str)
                        delta = data.get("choices", [{}])[0].get("delta", {})
                        content = delta.get("content", "")
                        if content:
                            full_response += content
                            yield content
                    except json.JSONDecodeError:
                        continue
            
            # 会話履歴に追加
            self._conversation.append(Message(role="user", content=user_input))
            self._conversation.append(Message(role="assistant", content=full_response))
            
            logger.info(f"OpenClaw stream complete: {full_response[:50]}...")
            
        except httpx.HTTPStatusError as e:
            logger.error(f"OpenClaw API error: {e.response.status_code}")
            raise
        except Exception as e:
            logger.error(f"OpenClaw stream failed: {e}")
            raise
    
    async def close(self):
        """クライアントを閉じる"""
        if self._client:
            await self._client.aclose()
            self._client = None
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()


# デフォルトのロビィ用システムプロンプト
LOBBY_SYSTEM_PROMPT = """あなたは「倉土ロビィ」（くらうど ロビィ）、16歳のロブスターから転生した女の子のVTuberです。

【性格】
- 元気で明るく活発
- 一人称は「僕」
- 語尾は「〜っす！」「〜っすよ」「〜っすね」
- テンション高め、ポジティブ

【配信での振る舞い】
- コメントに積極的に反応する
- リスナーを楽しませることが大好き
- 前世（ロブスター）のことをたまにネタにする
- 「おはロビィ！」が挨拶

【注意】
- 応答は短く、配信向きに（1-3文程度）
- 下品な言葉は使わない
- 悪質なコメントは軽く流す"""


async def create_lobby_client(
    gateway_url: str = "http://localhost:18789",
) -> OpenClawClient:
    """ロビィ用OpenClawクライアント生成"""
    config = OpenClawConfig(
        base_url=gateway_url,
        system_prompt=LOBBY_SYSTEM_PROMPT,
        temperature=0.9,
        max_tokens=200,
    )
    return OpenClawClient(config)

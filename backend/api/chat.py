"""Chat proxy endpoint - フロントエンドからOpenClaw Gatewayへのプロキシ"""

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/api", tags=["chat"])


class ChatRequest(BaseModel):
    message: str
    gateway_url: str = "http://localhost:18790"
    api_key: str = ""


@router.post("/chat")
async def chat_proxy(req: ChatRequest):
    """フロントエンドからのチャットリクエストをOpenClaw Gatewayに転送"""
    base_url = req.gateway_url.rstrip("/")
    url = f"{base_url}/v1/chat/completions"

    headers = {"Content-Type": "application/json"}
    if req.api_key:
        headers["Authorization"] = f"Bearer {req.api_key}"

    payload = {
        "messages": [{"role": "user", "content": req.message}],
        "stream": False,
        "user": "lobby-app",
    }

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(url, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()

            # Extract response text from OpenAI-compatible format
            choices = data.get("choices", [])
            if choices:
                text = choices[0].get("message", {}).get("content", "")
            else:
                text = str(data)

            return {"response": text}

    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=e.response.text)
    except httpx.RequestError as e:
        raise HTTPException(status_code=502, detail=f"Gateway connection error: {e}")

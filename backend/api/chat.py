"""Chat proxy endpoint - フロントエンドからOpenClaw Gatewayへのプロキシ

OpenClaw CLIの `openclaw agent` コマンドを使用して、
エージェントのパーソナリティ（SOUL.md等）が反映されたレスポンスを返す。
"""

import asyncio
import json

from pydantic import BaseModel
from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/api", tags=["chat"])


class ChatRequest(BaseModel):
    message: str
    gateway_url: str = "http://localhost:18790"  # unused but kept for compat
    api_key: str = ""
    session_id: str = "lobby-web"


@router.post("/chat")
async def chat_proxy(req: ChatRequest):
    """フロントエンドからのチャットリクエストをOpenClaw Agentに転送"""
    cmd = [
        "openclaw", "agent",
        "--session-id", req.session_id,
        "--message", req.message,
        "--json",
        "--timeout", "120",
    ]

    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=130)

        if proc.returncode != 0:
            err = stderr.decode().strip() if stderr else "Unknown error"
            raise HTTPException(status_code=502, detail=f"Agent error: {err}")

        data = json.loads(stdout.decode())

        if data.get("status") != "ok":
            raise HTTPException(
                status_code=502,
                detail=f"Agent returned status: {data.get('status')}",
            )

        # Extract text from payloads
        payloads = data.get("result", {}).get("payloads", [])
        texts = [p["text"] for p in payloads if p.get("text")]
        response_text = "\n".join(texts) if texts else ""

        return {"response": response_text}

    except asyncio.TimeoutError:
        raise HTTPException(status_code=504, detail="Agent timeout")
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=502, detail=f"Invalid agent response: {e}")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Agent connection error: {e}")

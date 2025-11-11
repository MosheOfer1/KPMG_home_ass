from __future__ import annotations
import httpx
from typing import Optional
from .config import ApiConfig
from ..core_models import ChatRequest, ChatResponse


class OrchestratorClient:
    def __init__(self, cfg: ApiConfig):
        self._cfg = cfg
        self._client = httpx.AsyncClient(timeout=cfg.request_timeout_s)

    async def chat(self, req: ChatRequest, *, request_id: Optional[str] = None) -> ChatResponse:
        url = f"{self._cfg.orchestrator_url}/v1/chat"
        headers = {"X-Request-ID": request_id} if request_id else None
        resp = await self._client.post(url, json=req.model_dump(mode="json"), headers=headers)
        resp.raise_for_status()
        return ChatResponse.model_validate(resp.json())

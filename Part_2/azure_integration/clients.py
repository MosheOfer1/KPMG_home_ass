from __future__ import annotations
import time
from typing import Iterable, List, Optional, Dict, Callable

from openai import AzureOpenAI
from openai._exceptions import APIError, RateLimitError, APITimeoutError

from .config import AzureOpenAIConfig
from .interfaces import ILLMClient, IEmbeddingsClient


TelemetryHook = Callable[[str, Dict], None]  # (event_name, payload)


def _retry_loop(fn, *, retries: int, backoff_base: float, on_error: Optional[TelemetryHook] = None):
    attempt = 0
    while True:
        try:
            return fn()
        except (RateLimitError, APITimeoutError, APIError) as e:
            attempt += 1
            if on_error:
                on_error("azure.request.error", {"attempt": attempt, "type": type(e).__name__, "message": str(e)})
            if attempt > retries:
                raise
            time.sleep(backoff_base * (2 ** (attempt - 1)))


class AzureChatClient(ILLMClient):
    """Thin Azure Chat adapter with optional JSON mode and simple retries."""

    def __init__(
        self,
        cfg: AzureOpenAIConfig,
        *,
        on_result: Optional[TelemetryHook] = None,
        on_error: Optional[TelemetryHook] = None,
    ):
        self.cfg = cfg
        self.client = AzureOpenAI(
            api_key=cfg.api_key,
            api_version=cfg.api_version,
            azure_endpoint=cfg.endpoint,
            timeout=cfg.request_timeout_s,
        )
        self.default_deployment = cfg.chat_deployment
        self.on_result = on_result
        self.on_error = on_error

    def chat(
        self,
        messages: List[Dict[str, str]],
        *,
        model: Optional[str] = None,
        max_tokens: Optional[int] = None,
        temperature: float = 0.2,
        json_mode: bool = False,
        extra_headers: Optional[Dict[str, str]] = None,
    ) -> str:
        deployment = model or self.default_deployment

        def _call():
            resp = self.client.chat.completions.create(
                model=deployment,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                response_format={"type": "json_object"} if json_mode else None,
                extra_headers=extra_headers,
            )
            return resp.choices[0].message.content or ""

        out = _retry_loop(
            _call,
            retries=self.cfg.max_retries,
            backoff_base=self.cfg.backoff_base_s,
            on_error=self.on_error,
        )
        if self.on_result:
            self.on_result(
                "azure.chat.success",
                {"deployment": deployment, "json_mode": json_mode, "len_messages": len(messages), "len_out": len(out)},
            )
        return out


class AzureEmbeddingsClient(IEmbeddingsClient):
    """Azure Embeddings adapter with batching + retries."""

    def __init__(
        self,
        cfg: AzureOpenAIConfig,
        *,
        default_deployment: Optional[str] = None,
        on_result: Optional[TelemetryHook] = None,
        on_error: Optional[TelemetryHook] = None,
    ):
        self.cfg = cfg
        self.client = AzureOpenAI(
            api_key=cfg.api_key,
            api_version=cfg.api_version,
            azure_endpoint=cfg.endpoint,
            timeout=cfg.request_timeout_s,
        )
        self.default_deployment = default_deployment or cfg.embeddings_deployment
        self.on_result = on_result
        self.on_error = on_error

    def embed_texts(
        self,
        texts: Iterable[str],
        *,
        model: Optional[str] = None,
        batch_size: int = 64,
    ) -> List[List[float]]:
        deployment = model or self.default_deployment
        texts_list = list(texts)
        vectors: List[List[float]] = []

        def _embed_batch(batch: List[str]) -> List[List[float]]:
            resp = self.client.embeddings.create(model=deployment, input=batch)
            # Azure returns in input order
            return [d.embedding for d in resp.data]

        for i in range(0, len(texts_list), batch_size):
            batch = texts_list[i : i + batch_size]
            chunk_vecs = _retry_loop(
                lambda: _embed_batch(batch),
                retries=self.cfg.max_retries,
                backoff_base=self.cfg.backoff_base_s,
                on_error=self.on_error,
            )
            vectors.extend(chunk_vecs)

        if self.on_result:
            self.on_result("azure.embed.success", {"deployment": deployment, "count": len(texts_list)})
        return vectors

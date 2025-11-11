from __future__ import annotations
from typing import Iterable, List, Protocol, Optional, Dict


class ILLMClient(Protocol):
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
        """Return assistant text (JSON string if json_mode=True)."""
        ...


class IEmbeddingsClient(Protocol):
    def embed_texts(
        self,
        texts: Iterable[str],
        *,
        model: Optional[str] = None,
        batch_size: int = 64,
    ) -> List[List[float]]:
        """Return embeddings for each text, preserving order."""
        ...

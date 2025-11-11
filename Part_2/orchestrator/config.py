from __future__ import annotations
import os
from dataclasses import dataclass

@dataclass(frozen=True)
class OrchestratorConfig:
    # Retrieval knobs (consumed at query time)
    top_k: int = int(os.getenv("RETRIEVER_TOP_K", "6"))
    max_context_chars: int = int(os.getenv("MAX_CONTEXT_CHARS", "12000"))

    # Timeouts / tracing
    request_timeout_s: float = float(os.getenv("ORCH_TIMEOUT_S", "30"))

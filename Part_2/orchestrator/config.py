from __future__ import annotations
import os
from dataclasses import dataclass

@dataclass(frozen=True)
class OrchestratorConfig:
    """
    Represents configuration settings for the orchestrator.

    This class encapsulates configuration parameters needed for the orchestrator,
    including retrieval settings, context and history size limits, and request
    timeout duration. The class is designed as an immutable dataclass, ensuring
    that its instances cannot be modified after creation, promoting configurational
    consistency throughout runtime.

    Attributes:
        top_k: Number of top results to retrieve during query processing.
        max_context_chars: Maximum allowable characters in the context.
        max_history_chars: Maximum allowable characters in the history.
        request_timeout_s: Timeout duration for requests, in seconds.
    """
    # Retrieval knobs (consumed at query time)
    top_k: int = int(os.getenv("RETRIEVER_TOP_K", "6"))
    max_context_chars: int = int(os.getenv("MAX_CONTEXT_CHARS", "12000"))
    max_history_chars: int = int(os.getenv("MAX_HISTORY_CHARS", "42000"))
    # Timeouts / tracing
    request_timeout_s: float = float(os.getenv("ORCH_TIMEOUT_S", "45"))

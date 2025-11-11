from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Protocol

from Part_2.core_models import HMO, Tier


@dataclass(frozen=True)
class KBItem:
    """
    Read-only view of a knowledge-base chunk that callers receive from searches.
    This keeps your public surface stable even if the underlying KBChunk evolves.
    """
    text: str
    source_uri: str
    hmo: Optional[HMO]
    tier_tags: tuple[str, ...]
    section: Optional[str]
    service: Optional[str]
    kind: str  # "benefit" | "contact" | "service" | "blurb"


class IKnowledgeBase(Protocol):
    """
    Minimal interface for a searchable KB implementation.

    Implementations should be immutable for read operations after construction
    (i.e., thread-safe for concurrent .search calls).
    """

    def search(
        self,
        query: str,
        *,
        hmo: Optional[HMO],
        tier: Optional[Tier],
        top_k: int = 6,
    ) -> List[KBItem]:
        """Return up to top_k most relevant KB items for the query,
        optionally biased by HMO/tier."""
        ...

    @property
    def fingerprint(self) -> str:
        """A content/deployment fingerprint suitable for cache keys and tests."""
        ...

    @property
    def size(self) -> int:
        """Number of items indexed (useful for health checks & tests)."""
        ...

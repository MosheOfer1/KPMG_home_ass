from __future__ import annotations
import os
from dataclasses import dataclass

@dataclass(frozen=True)
class RetrieverConfig:
    kb_dir: str = os.getenv("PHASE2_DATA_DIR", "Part_2/phase2_data")
    embeddings_deployment: str = os.getenv("AZURE_OPENAI_EMBED_DEPLOYMENT", "text-embedding-ada-002")
    cache_dir: str = os.getenv("RETRIEVER_CACHE_DIR", "Part_2/.kb_cache")

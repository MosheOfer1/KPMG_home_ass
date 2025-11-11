from __future__ import annotations
import os
from pathlib import Path

import pytest

from Part_2.azure_integration import AzureEmbeddingsClient, load_config
from Part_2.core_models import HMO, Tier
from Part_2.retriever.config import RetrieverConfig
from Part_2.retriever.kb import HtmlKB


@pytest.fixture(scope="session")
def kb_dir() -> Path:
    kb_path = Path(os.getenv("PHASE2_DATA_DIR", "Part_2/phase2_data")).resolve()
    assert kb_path.exists(), f"KB directory not found: {kb_path}"
    htmls = list(kb_path.rglob("*.html"))
    assert htmls, f"No HTML files found in {kb_path}"
    return kb_path


@pytest.fixture(scope="session")
def retriever_config(kb_dir: Path) -> RetrieverConfig:
    cfg = RetrieverConfig(kb_dir=str(kb_dir))
    os.makedirs(cfg.cache_dir, exist_ok=True)
    return cfg


@pytest.fixture(scope="session")
def embedder() -> AzureEmbeddingsClient:
    aoai_cfg = load_config()
    return AzureEmbeddingsClient(aoai_cfg, default_deployment=os.getenv("AZURE_OPENAI_EMBED_DEPLOYMENT", "ada-002"))


def test_kb_functionality_and_cache(retriever_config: RetrieverConfig, embedder: AzureEmbeddingsClient):
    """Ensure the KB builds successfully and cache is reused."""
    kb = HtmlKB(
        retriever_config.kb_dir,
        embedder,
        cache_dir=retriever_config.cache_dir,
        embeddings_deployment=retriever_config.embeddings_deployment,
    )

    # Expect at least one chunk
    assert len(kb._chunks) > 0, "Expected KB to have parsed at least one HTML chunk"

    # Cache should exist
    cached = list(Path(retriever_config.cache_dir).glob("kb_*.pkl"))
    assert cached, "Expected a cache file to be created after building KB"

    # Re-load from cache (should be instantaneous)
    kb2 = HtmlKB(
        retriever_config.kb_dir,
        embedder,
        cache_dir=retriever_config.cache_dir,
        embeddings_deployment=retriever_config.embeddings_deployment,
    )
    assert len(kb2._chunks) == len(kb._chunks), "Cache reload should yield same number of chunks"

    # Run a basic retrieval test
    result = kb2.search("שירותים רפואיים", hmo=HMO.MACCABI, tier=Tier.GOLD, top_k=3)
    assert isinstance(result, list)
    assert all(hasattr(r, "text") for r in result)
    print(f"Retrieved {len(result)} snippets; top source = {result[0].source_uri if result else 'N/A'}")

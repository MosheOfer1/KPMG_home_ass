"""
Basic smoke test for Azure Embeddings client connectivity.
Requires valid AZURE_OPENAI_* env vars and an embeddings deployment.
"""
from ..clients import AzureEmbeddingsClient
from ..config import load_config


def test_embeddings_generate_vector():
    cfg = load_config()
    client = AzureEmbeddingsClient(cfg)
    vecs = client.embed_texts(["שלום", "hello world"])
    assert isinstance(vecs, list)
    assert len(vecs) == 2
    v = vecs[0]
    assert all(isinstance(x, float) for x in v)
    # embedding dimensionality should be >100
    assert len(v) > 100

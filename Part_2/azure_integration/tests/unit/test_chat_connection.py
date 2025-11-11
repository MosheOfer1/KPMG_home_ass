"""
Basic smoke test for Azure Chat client connectivity.
Requires valid AZURE_OPENAI_* env vars and deployed chat model.
Mark as 'network' so CI can skip it by default.
"""
import pytest

from Part_2.azure_integration import load_config, AzureChatClient

pytestmark = pytest.mark.network


def test_chat_completion_roundtrip():
    cfg = load_config()
    client = AzureChatClient(cfg)
    out = client.chat(
        messages=[
            {"role": "system", "content": "You are a concise assistant."},
            {"role": "user", "content": "Say 'pong'."},
        ],
        model=cfg.chat_deployment,  # or qna, any valid deployment
        max_tokens=10,
        temperature=0.0,
    )
    assert isinstance(out, str)
    assert "pong" in out.lower()

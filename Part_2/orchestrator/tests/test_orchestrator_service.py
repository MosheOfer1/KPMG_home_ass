from __future__ import annotations

import pytest

from ...azure_integration import load_config, AzureEmbeddingsClient, AzureChatClient
from ...core_models import SessionBundle, Locale, Phase, UserProfile, ChatRequest, ChatResponse, Gender
from ...orchestrator.config import OrchestratorConfig
from ...orchestrator.service import OrchestratorService
from ...retriever.config import RetrieverConfig
from ...retriever.kb import HtmlKB


@pytest.mark.asyncio
async def test_orchestrator_service_handle_chat_real_request(cfgs):
    orch_cfg, aoai_cfg, ret_cfg = cfgs
    embedder = AzureEmbeddingsClient(aoai_cfg, default_deployment=ret_cfg.embeddings_deployment,
                                     on_error=lambda event_name, payload: print("telemetry %s: %s", event_name,
                                                                                   payload))
    kb = HtmlKB(
        ret_cfg.kb_dir,
        embedder,
        cache_dir=ret_cfg.cache_dir,
        embeddings_deployment=ret_cfg.embeddings_deployment,
    )
    chat_client = AzureChatClient(aoai_cfg)

    svc = OrchestratorService(
        orch_cfg=orch_cfg,
        embedder=embedder,
        chat_client=chat_client,
        kb=kb,
    )
    # Minimal starting session (incomplete profile → INFO phase)
    sb = SessionBundle(
        locale=Locale.HE,
        phase=Phase.INFO_COLLECTION,
        user_profile=UserProfile()
    )
    req = ChatRequest(
        user_input="השם שלי משה עופר וזה התעודת זהות שלי 209931534",
        session_bundle=sb
    )

    resp: ChatResponse = await svc.handle_chat(req, request_id="t-1")

    # --- Basic response checks ---
    assert isinstance(resp, ChatResponse)
    assert isinstance(resp.user_profile, UserProfile)
    assert resp.assistant_text
    assert resp.suggested_phase == Phase.INFO_COLLECTION  # still collecting info

    p = resp.user_profile

    # --- Field update checks ---
    # These should have been filled
    assert p.first_name == "משה"
    assert p.last_name == "עופר"
    assert p.id_number == "209931534"

    # These should remain untouched (None/default)
    assert p.gender is Gender.UNSPECIFIED or str(p.gender).lower() == "unspecified"
    assert p.birth_year is None
    assert p.hmo_name is None
    assert p.hmo_card_number is None
    assert p.membership_tier is None

    # --- Consistency checks ---
    # Phase should persist from session
    assert resp.suggested_phase == Phase.INFO_COLLECTION

    # Validation flags should only include missing fields
    missing = {"gender", "birth_year", "hmo_name", "hmo_card_number", "membership_tier"}
    assert all(any(m in f for m in missing) for f in resp.validation_flags)

# ---------
# Fakes
# ---------
class FakeChatClient:
    """Deterministic LLM stub; payload is switched per-test via .response."""
    def __init__(self, response: str):
        self.response = response
        self.calls = []

    def chat(self, messages, temperature: float, max_tokens: int, *args ,**kwargs) -> str:
        # capture for assertions if needed
        self.calls.append({"messages": messages, "temperature": temperature, "max_tokens": max_tokens})
        return self.response

# ----------
# Fixtures
# ----------
@pytest.fixture
def cfgs():
    orch_cfg = OrchestratorConfig()
    aoai_cfg = load_config()
    ret_cfg = RetrieverConfig()
    return orch_cfg, aoai_cfg, ret_cfg

# ---------------
# Tests: INFO phase
# ---------------
@pytest.mark.asyncio
async def test_orchestrator_service_handle_chat_fake_request(cfgs):
    orch_cfg, aoai_cfg, ret_cfg = cfgs
    embedder = AzureEmbeddingsClient(aoai_cfg, default_deployment=ret_cfg.embeddings_deployment,
                                     on_error=lambda event_name, payload: print("telemetry %s: %s", event_name,
                                                                                payload))
    kb = HtmlKB(
        ret_cfg.kb_dir,
        embedder,
        cache_dir=ret_cfg.cache_dir,
        embeddings_deployment=ret_cfg.embeddings_deployment,
    )
    chat_client = AzureChatClient(aoai_cfg)

    svc = OrchestratorService(
        orch_cfg=orch_cfg,
        embedder=embedder,
        chat_client=chat_client,
        kb=kb,
    )

    # LLM returns well-formed JSON with a profile patch + CONFIRMED
    info_json = """
    {
      "assistant_say": "מעולה, אישרתי את הפרטים.",
      "profile_patch": {
        "first_name": "Moshe",
        "last_name": "Ofer",
        "id_number": "123456789",
        "gender": "male",
        "birth_year": 1997,
        "hmo_name": "maccabi",
        "hmo_card_number": "987654321",
        "membership_tier": "gold"
      },
      "status": "CONFIRMED"
    }
    """
    svc.chat_client = FakeChatClient(response=info_json)

    # Minimal starting session (incomplete profile → INFO phase)
    sb = SessionBundle(
        locale=Locale.HE,
        phase=Phase.INFO_COLLECTION,
        user_profile=UserProfile()
    )
    req = ChatRequest(user_input="השם שלי משה עופר", session_bundle=sb)

    resp: ChatResponse = await svc.handle_chat(req, request_id="t-1")

    # Assertions
    assert isinstance(resp, ChatResponse)
    assert "אשר" in resp.assistant_text or "מעולה" in resp.assistant_text
    # Service suggests moving to QNA once confirmed and valid
    assert resp.suggested_phase == Phase.QNA

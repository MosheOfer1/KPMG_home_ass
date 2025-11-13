# services/api_gateway/tests/unit/test_api.py
from __future__ import annotations
import pytest
from httpx import AsyncClient, ASGITransport

from ..app import app, orch
from Part_2.core_models import (
    ChatRequest, UserProfile, Gender, HMO, Tier, Locale,
    ConversationHistory, Turn, SessionBundle, Phase, ChatResponse
)


@pytest.fixture
def sample_request() -> ChatRequest:
    profile = UserProfile(
        first_name="Dana",
        last_name="Levi",
        id_number="012345678",
        gender=Gender.FEMALE,
        birth_year=1992,
        hmo_name=HMO.MACCABI,
        hmo_card_number="123456789",
        membership_tier=Tier.GOLD,
    )
    history = ConversationHistory(turns=[Turn(user_text="שלום", assistant_text="היי")])
    bundle = SessionBundle(user_profile=profile, history=history, phase=Phase.INFO_COLLECTION)
    return ChatRequest(session_bundle=bundle, user_input="מה הכיסוי לביקור רופא?")


@pytest.mark.asyncio
async def test_health_ok():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        r = await ac.get("/health")
    assert r.status_code == 200
    assert r.json() == {"ok": True}


@pytest.mark.asyncio
async def test_chat_success(monkeypatch, sample_request):
    async def fake_chat(req, request_id=None) -> ChatResponse:
        return ChatResponse(
            assistant_text="במכבי זהב הביקור עולה 25₪.",
            suggested_phase=Phase.QNA,
            citations=["kb://maccabi/visits#copay"],
            validation_flags=[],
            trace_id="trace-123",
            user_profile=UserProfile()
        )

    monkeypatch.setattr(orch, "chat", fake_chat)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        r = await ac.post("/chat", json=sample_request.model_dump(mode="json"))

    assert r.status_code == 200
    body = r.json()
    assert body["assistant_text"].startswith("במכבי")
    assert body["suggested_phase"] == Phase.QNA.value
    assert "X-Request-ID" in r.headers


@pytest.mark.asyncio
async def test_chat_upstream_error(monkeypatch, sample_request):
    async def boom(req, request_id=None):
        raise RuntimeError("orchestrator down")

    monkeypatch.setattr(orch, "chat", boom)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        r = await ac.post("/chat", json=sample_request.model_dump(mode="json"))

    assert r.status_code == 502
    assert "Upstream error" in r.json()["detail"]

# orchestrator.py
from __future__ import annotations
import json, logging, uuid
from typing import Dict, List, Tuple, Any

from .config import OrchestratorConfig
from .prompts import sys_prompt_info, sys_prompt_qna, user_instructions_qna
from ..azure_integration import AzureOpenAIConfig, AzureEmbeddingsClient, AzureChatClient
from ..core_models import ChatRequest, ChatResponse, Locale, Phase, SessionBundle, UserProfile
from ..retriever.config import RetrieverConfig
from ..retriever.kb import HtmlKB

log = logging.getLogger("orchestrator")

# ---------------------------
# Helpers
# ---------------------------
def _is_profile_complete_and_valid(p: UserProfile) -> Tuple[bool, List[str]]:
    problems: List[str] = []
    if not p.first_name: problems.append("first_name missing")
    if not p.last_name: problems.append("last_name missing")
    if not p.id_number: problems.append("id_number missing (9 digits)")
    if not p.gender or str(getattr(p.gender, "value", p.gender)).lower() == "unspecified":
        problems.append("gender missing")
    if not p.birth_year:
        problems.append("birth_year missing")
    if not p.hmo_name: problems.append("hmo_name missing")
    if not p.hmo_card_number: problems.append("hmo_card_number missing (9 digits)")
    if not p.membership_tier: problems.append("membership_tier missing")
    return len(problems) == 0, problems


log = logging.getLogger("orchestrator.service")

def _merge_patch(profile: UserProfile, patch: Dict[str, Any]) -> UserProfile:
    """Safely merge partial user data without breaking validation."""
    HMO = {"maccabi": "מכבי", "meuhedet": "מאוחדת", "clalit": "כללית"}
    TIER = {"gold": "זהב", "silver": "כסף", "bronze": "ארד"}
    GENDER = {"male": "male", "female": "female", "זכר": "male", "נקבה": "female"}

    data = profile.model_dump()

    for k, v in (patch or {}).items():
        if v is None:
            continue
        if isinstance(v, str):
            v = v.strip().lower()

        try:
            if k == "hmo_name":
                v = HMO.get(v, v)
            elif k == "membership_tier":
                v = TIER.get(v, v)
            elif k == "gender":
                v = GENDER.get(v, v)
            elif k == "birth_year" and isinstance(v, str) and v.isdigit():
                v = int(v)
            elif k in {"id_number", "hmo_card_number"}:
                v = str(v).strip()
            data[k] = v
        except Exception as e:
            log.warning(f"Ignoring bad field {k}: {v!r} ({e})")

    try:
        return UserProfile(**data)
    except Exception as e:
        log.warning(f"Profile validation failed: {e}")
        # Fallback to original profile if something still invalid
        return profile

# ---------------------------
# Service
# ---------------------------
class OrchestratorService:
    def __init__(self, orch_cfg: OrchestratorConfig, aoai_cfg: AzureOpenAIConfig, ret_cfg: RetrieverConfig):
        self.cfg = orch_cfg
        self.embedder = AzureEmbeddingsClient(aoai_cfg, default_deployment=ret_cfg.embeddings_deployment)
        self.kb = HtmlKB(
            ret_cfg.kb_dir,
            self.embedder,
            cache_dir=ret_cfg.cache_dir,
            embeddings_deployment=ret_cfg.embeddings_deployment,
        )
        self.chat_client = AzureChatClient(aoai_cfg)

    async def handle_chat(self, req: ChatRequest, *, request_id: str | None = None) -> ChatResponse:
        sb = req.session_bundle
        locale = sb.locale or sb.user_profile.locale or Locale.HE

        # Stay in INFO until explicitly confirmed and valid
        if sb.phase == Phase.INFO_COLLECTION:
            return await self._turn_info(req, locale, request_id)
        return await self._turn_qna(req, locale, request_id)

    # ---------------------------
    # Info phase (LLM-driven JSON contract)
    # ---------------------------
    async def _turn_info(self, req: ChatRequest, locale: Locale, request_id: str | None) -> ChatResponse:
        sb: SessionBundle = req.session_bundle
        profile = sb.user_profile
        user_text = req.user_input

        complete, problems = _is_profile_complete_and_valid(profile)
        sys_msg = sys_prompt_info(locale)
        profile_json = profile.model_dump()

        messages = [
            {"role": "system", "content": sys_msg},
            {"role": "system", "content": f"PROFILE_SNAPSHOT_JSON: {json.dumps(profile_json, ensure_ascii=False)}"},
            {"role": "system", "content": f"VALIDATION: {'OK' if complete else 'MISSING/INVALID -> ' + '; '.join(problems)}"},
            {"role": "user", "content": user_text},
        ]

        # Important: request structured JSON
        raw = self.chat_client.chat(
            messages, temperature=0.2, max_tokens=350
        )
        parsed = json.loads(raw)

        assistant_say = (parsed.get("assistant_say") or "").strip()
        patch = parsed.get("profile_patch") or {}
        status = (parsed.get("status") or "ASKING").upper()

        # Merge & revalidate after LLM patch
        new_profile = _merge_patch(profile, patch)
        now_complete, _ = _is_profile_complete_and_valid(new_profile)

        # Decide phase and confirmation flag
        suggested_phase = Phase.INFO_COLLECTION
        getattr(sb, "info_confirmed", False)

        if status == "CONFIRMED" and now_complete:
            suggested_phase = Phase.QNA

        # (Controller responsibility) Persist sb.user_profile <- new_profile and sb.info_confirmed <- info_confirmed
        # If you handle persistence here, you can attach them to ChatResponse via trace or a side channel.

        return ChatResponse(
            assistant_text=assistant_say or ("OK." if locale != Locale.HE else "אוקיי."),
            suggested_phase=suggested_phase,
            citations=[],
            validation_flags=[],
            user_profile=new_profile,
            trace_id=request_id or str(uuid.uuid4()),
        )

    # ---------------------------
    # Q&A phase (grounded with KB)
    # ---------------------------
    async def _turn_qna(self, req: ChatRequest, locale: Locale, request_id: str | None) -> ChatResponse:
        profile = req.session_bundle.user_profile
        query = req.user_input

        hints: List[str] = []
        if profile.hmo_name: hints.append(str(profile.hmo_name.value))
        if profile.membership_tier: hints.append(str(profile.membership_tier.value))
        retrieval_query = " | ".join([query] + hints) if hints else query

        found = self.kb.search(
            retrieval_query, hmo=profile.hmo_name, tier=profile.membership_tier, top_k=self.cfg.top_k
        )

        parts: List[str] = []
        citations: List[str] = []
        for i, ch in enumerate(found, start=1):
            parts.append(f"[{i}] {ch.text}")
            citations.append(ch.source_uri)
        context_blob = "\n\n".join(parts)
        if len(context_blob) > self.cfg.max_context_chars:
            context_blob = context_blob[: self.cfg.max_context_chars] + "\n…"

        sys_msg = sys_prompt_qna(locale)
        user_instr = user_instructions_qna(locale)
        profile_line = (
            f"HMO={getattr(profile.hmo_name,'value',profile.hmo_name)} | "
            f"Tier={getattr(profile.membership_tier,'value',profile.membership_tier)} | "
            f"Gender={getattr(profile.gender,'value',profile.gender)} | "
            f"BirthYear={profile.birth_year}"
        )

        messages = [
            {"role": "system", "content": sys_msg},
            {"role": "system", "content": f"Knowledge snippets:\n{context_blob}"},
            {"role": "system", "content": f"User {profile_line}"},
            {"role": "user", "content": f"{user_instr}\n\n{query}"},
        ]

        answer = self.chat_client.chat(messages, temperature=0.2, max_tokens=600)
        return ChatResponse(
            assistant_text=answer,
            suggested_phase=Phase.QNA,
            citations=citations,
            user_profile=profile,
            validation_flags=[],
            trace_id=request_id or str(uuid.uuid4()),
        )

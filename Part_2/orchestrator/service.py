from __future__ import annotations

import json
import logging
import uuid
from typing import Dict, List

from .config import OrchestratorConfig
from .prompts import sys_prompt_info, sys_prompt_qna, user_instructions_qna
from .utils import _is_profile_complete_and_valid, _history_to_messages, _merge_patch, parse_llm_json
from ..azure_integration import AzureOpenAIConfig, AzureEmbeddingsClient, AzureChatClient
from ..core_models import ChatRequest, ChatResponse, Locale, Phase, SessionBundle, Turn
from ..retriever.config import RetrieverConfig
from ..retriever.kb import HtmlKB

log = logging.getLogger("orchestrator")

def _telemetry_hook(event_name: str, payload: dict):
    log.info("telemetry %s: %s", event_name, payload)


# ---------------------------
# Service
# ---------------------------
class OrchestratorService:
    def __init__(self, orch_cfg: OrchestratorConfig, aoai_cfg: AzureOpenAIConfig, ret_cfg: RetrieverConfig):
        self.cfg = orch_cfg
        self.embedder = AzureEmbeddingsClient(aoai_cfg, default_deployment=ret_cfg.embeddings_deployment, on_error=_telemetry_hook)
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

        # Convert past turns to messages
        history_msgs = _history_to_messages(sb.history, max_chars=self.cfg.max_history_chars)

        messages: List[Dict[str, str]] = [
            {"role": "system", "content": sys_msg},
            {"role": "system", "content": f"PROFILE_SNAPSHOT_JSON: {json.dumps(profile_json, ensure_ascii=False)}"},
            {"role": "system", "content": f"VALIDATION: {'OK' if complete else 'MISSING/INVALID -> ' + '; '.join(problems)}"},
        ]

        # Insert conversation history (if any), before the latest user input
        messages.extend(history_msgs)

        # Latest user input as the last user message
        messages.append({"role": "user", "content": user_text})

        # Important: request structured JSON
        try:
            raw = self.chat_client.chat(
                messages, temperature=0.2, max_tokens=350, json_mode=True
            )
        except Exception as e:
            log.exception("LLM error during info phase", extra={"request_id": request_id})
            # User-safe fallback
            fallback_text = (
                "⚠️ הייתה בעיה טכנית בעיבוד הבקשה. "
                "אנא נסה/י שוב בעוד מספר רגעים."
            ) if locale == Locale.HE else (
                "⚠️ There was a technical problem handling your request. "
                "Please try again in a moment."
            )
            # Keep phase as INFO_COLLECTION and don’t mutate profile
            return ChatResponse(
                assistant_text=fallback_text,
                suggested_phase=Phase.INFO_COLLECTION,
                citations=[],
                validation_flags=["LLM_ERROR"],
                user_profile=profile,
                trace_id=request_id or str(uuid.uuid4()),
            )

        parsed = parse_llm_json(raw)

        assistant_say = (parsed.get("assistant_say") or "").strip()
        patch = parsed.get("profile_patch") or {}
        status = (parsed.get("status") or "ASKING").upper()
        sb.history.turns.append(
            Turn(
                user_text=user_text,
                assistant_text=assistant_say
            )
        )

        # Merge & revalidate after LLM patch
        new_profile = _merge_patch(profile, patch, request_id)
        now_complete, _ = _is_profile_complete_and_valid(new_profile)

        suggested_phase = Phase.INFO_COLLECTION
        getattr(sb, "info_confirmed", False)

        if status == "CONFIRMED" and now_complete:
            suggested_phase = Phase.QNA

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
        sb = req.session_bundle
        profile = sb.user_profile
        query = req.user_input

        # 1) Retrieval
        try:
            hints: List[str] = []
            if profile.hmo_name: hints.append(str(profile.hmo_name.value))
            if profile.membership_tier: hints.append(str(profile.membership_tier.value))
            retrieval_query = " | ".join([query] + hints) if hints else query

            found = self.kb.search(
                retrieval_query, hmo=profile.hmo_name, tier=profile.membership_tier, top_k=self.cfg.top_k
            )
        except Exception as e:
            log.exception("KB search error", extra={"request_id": request_id})
            fallback = (
                "⚠️ אני נתקל בבעיה בגישה למידע כרגע. "
                "אפשר לנסות שוב מאוחר יותר, או לפנות ישירות לקופת החולים."
            ) if locale == Locale.HE else (
                "⚠️ I'm having trouble accessing the knowledge base right now. "
                "Please try again later or contact your HMO directly."
            )
            return ChatResponse(
                assistant_text=fallback,
                suggested_phase=Phase.QNA,
                citations=[],
                user_profile=profile,
                validation_flags=["KB_ERROR"],
                trace_id=request_id or str(uuid.uuid4()),
            )

        # 2) If retrieval returns nothing – handle gracefully
        if not found:
            log.info("No KB results for query", extra={"request_id": request_id})
            msg = (
                "לא מצאתי מידע רלוונטי לשאלה הזאת במסמכים שברשותי. "
                "נסה/י לשאול אחרת או לפנות לקופת החולים לקבלת מידע מדויק."
            ) if locale == Locale.HE else (
                "I couldn't find relevant information for this question "
                "in the documents I have. Try rephrasing, or contact your HMO directly."
            )
            return ChatResponse(
                assistant_text=msg,
                suggested_phase=Phase.QNA,
                citations=[],
                user_profile=profile,
                validation_flags=["NO_KB_MATCH"],
                trace_id=request_id or str(uuid.uuid4()),
            )

        parts: List[str] = []
        citations: List[str] = []
        for i, ch in enumerate(found, start=1):
            parts.append(f"[{i}] {ch.section} | {ch.service} | {ch.hmo} | {ch.tier_tags} | {ch.text} | {ch.source_uri} | {ch.kind}")
            citations.append(ch.source_uri)
        context_blob = "\n\n".join(parts)
        if len(context_blob) > self.cfg.max_context_chars:
            context_blob = context_blob[: self.cfg.max_context_chars] + "\n…"

        sys_msg = sys_prompt_qna(locale)
        user_instr = user_instructions_qna(locale)
        profile_line = (
            f"HMO={getattr(profile.hmo_name, 'value', profile.hmo_name)} | "
            f"Tier={getattr(profile.membership_tier, 'value', profile.membership_tier)} | "
            f"Gender={getattr(profile.gender, 'value', profile.gender)} | "
            f"BirthYear={profile.birth_year}"
        )

        # History messages
        history_msgs = _history_to_messages(sb.history, max_chars=self.cfg.max_history_chars)

        messages: List[Dict[str, str]] = [
            {"role": "system", "content": sys_msg},
            {"role": "system", "content": f"Knowledge snippets:\n{context_blob}"},
            {"role": "system", "content": f"User {profile_line}"},
        ]

        # Insert the past conversation before the current question
        messages.extend(history_msgs)

        # Finally, the new question with instructions
        messages.append(
            {"role": "user", "content": f"{user_instr}\n\n{query}"}
        )

        answer = self.chat_client.chat(messages, temperature=0.2, max_tokens=600)
        sb.history.turns.append(
            Turn(
                user_text=query,
                assistant_text=answer,
                citations=citations
            )
        )

        return ChatResponse(
            assistant_text=answer,
            suggested_phase=Phase.QNA,
            citations=citations,
            user_profile=profile,
            validation_flags=[],
            trace_id=request_id or str(uuid.uuid4()),
        )


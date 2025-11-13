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
    """
    OrchestratorService is responsible for coordinating interactions between various components
    such as an embedding client, knowledge base, and chat client to provide contextually aware chat
    responses.

    This class contains the logic for handling chat requests, including phases like Info Collection
    and Q&A, utilizing machine learning models and a structured knowledge base for response generation.
    It implements robust error handling and graceful fallback mechanisms when issues occur.

    Attributes:
        cfg (OrchestratorConfig): Configuration parameters for the orchestrator.
        embedder (AzureEmbeddingsClient): Client for embedding operations.
        kb (HtmlKB): Knowledge base object for document retrieval and search.
        chat_client (AzureChatClient): Chat client to interact with Azure OpenAI services.
    """
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
        """
        Handles the information-gathering phase of a chat interaction.

        This asynchronous method processes a user's input to gather relevant
        information based on their profile and previous chat history. It verifies
        the completeness and validity of the user's profile, formats the conversation
        into a sequence of messages, and sends a request to an external chat client
        for a response. The method also constructs fallback responses for failures
        and applies JSON-based updates to the user's profile based on the chat
        client's response. Finally, it determines the next chat phase based on
        the updated profile and response status.

        Arguments:
            req: The incoming chat request containing user input, the session bundle,
                and other associated information.
            locale: The locale or language setting for the current interaction.
            request_id: A unique string identifying the specific chat interaction.
                May be None.

        Returns:
            A ChatResponse object encapsulating the assistant's response text,
            the suggested next phase of the interaction, validation flags,
            the updated user profile, and a trace ID for debugging purposes.
        """
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
        """
        Handles the Q&A process, including retrieval of knowledge base entries, assembling context,
        and generating a conversational response.

        This function is designed to facilitate a chatbot's ability to retrieve relevant information
        from a knowledge base (KB) and provide meaningful, contextual responses to user queries.
        It operates in multiple stages: retrieval of documents from the KB, construction of
        a response context, and interaction with a conversational AI model to generate a reply.

        Parameters:
            req (ChatRequest): The chat request from the user, encapsulating their input and session details.
            locale (Locale): The locale specifying the language/region for the response.
            request_id (str | None): An optional unique identifier for tracking the request.

        Returns:
            ChatResponse: The chatbot's response, including the generated text, any relevant metadata,
            and a trace ID.

        Raises:
            Exception: If an error occurs during KB searches or other operations. This is only logged
            internally within the function.
        """
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


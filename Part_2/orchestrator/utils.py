from __future__ import annotations

import json
import logging
from typing import Dict, List, Tuple, Any

from ..core_models import UserProfile, ConversationHistory

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

def _merge_patch(profile: UserProfile, patch: Dict[str, Any], request_id) -> UserProfile:
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
            log.warning(f"Ignoring bad field {k}: {v!r} ({e})", extra={"request_id": request_id})

    try:
        return UserProfile(**data)
    except Exception as e:
        log.warning(f"Profile validation failed: {e}", extra={"request_id": request_id})
        # Fallback to original profile if something still invalid
        return profile

def _history_to_messages(
    history: ConversationHistory,
    max_chars: int
) -> List[Dict[str, str]]:
    """
    Convert ConversationHistory into OpenAI-style messages.
    Keeps only the most recent content up to max_chars.
    """
    msgs: List[Dict[str, str]] = []

    # Flatten turns into role/content messages
    for t in history.turns:
        if t.user_text:
            msgs.append({"role": "user", "content": t.user_text})
        if t.assistant_text:
            msgs.append({"role": "assistant", "content": t.assistant_text})

    # Trim from the *left* if too long
    def total_chars(ms: List[Dict[str, str]]) -> int:
        return sum(len(m["content"]) for m in ms)

    while msgs and total_chars(msgs) > max_chars:
        msgs.pop(0)

    return msgs


def parse_llm_json(text: str) -> Dict[str, Any]:
    if not text or not isinstance(text, str):
        return _fallback_json()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return _fallback_json()


def _fallback_json() -> Dict[str, Any]:
    """
    Always return a safe structure for the medical chatbot.
    """
    return {
        "assistant_say": "⚠️ לא הצלחתי לפענח את התשובה. אנא נסה שוב.",
        "profile_patch": {},
        "status": "ASKING",
    }


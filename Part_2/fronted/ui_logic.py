from __future__ import annotations
import logging
import os
import re
import urllib.parse
import uuid
from typing import List, Tuple

import httpx

from ..core_models import (
    ChatResponse, ChatRequest, SessionBundle,
    UserProfile, ConversationHistory, Phase, Locale, Turn
)
from ..logging_config import setup_logging
setup_logging("frontend")
log = logging.getLogger(__name__)

API_BASE = "http://localhost:8000"
MAX_TURNS = 20

TRANSLATIONS = {
    "he": {
        "title": "🩺 MicroChat Medical",
        "subtitle": "ייעוץ רפואי חכם ואישי",
        "placeholder": "שאל/י שאלה רפואית...",
        "send": "שלח",
        "error": "⚠️ שגיאה",
        "sources": "מקורות",
        "phase_info": "איסוף פרטים",
        "phase_qa": "שאלות ותשובות",
        "language": "שפה",
        "system_intro": """שלום! אני עוזר רפואי חכם שנועד לסייע לך בשאלות הנוגעות לשירותים רפואיים של קופות החולים הישראליות.

**אני יכול לעזור לך עם:**
• מידע על שירותים של מכבי, מאוחדת וכללית
• מענה מותאם אישית בהתאם לקופת החולים שלך
• הכוונה לשירותים רלוונטיים
• מענה לשאלות כלליות על זכויות וטיפולים

**כיצד אני עובד:**
1. תחילה אאסוף ממך מידע בסיסי (קופת חולים, גיל וכו')
2. לאחר מכן אוכל לענות על שאלות ספציפיות בצורה מדויקת

אנא שתף/י אותי בפרטים הרלוונטיים שלך, ואני אשמח לעזור!"""
    },
    "en": {
        "title": "🩺 MicroChat Medical",
        "subtitle": "Smart & Personalized Medical Consultation",
        "placeholder": "Ask a medical question...",
        "send": "Send",
        "error": "⚠️ Error",
        "sources": "Sources",
        "phase_info": "Info Collection",
        "phase_qa": "Q&A",
        "language": "Language",
        "system_intro": """Hello! I'm a smart medical assistant designed to help you with questions about Israeli health fund services.

**I can help you with:**
• Information about services from Maccabi, Meuhedet, and Clalit
• Personalized answers based on your health fund
• Guidance to relevant services
• Answers to general questions about rights and treatments

**How I work:**
1. First, I'll collect basic information from you (health fund, age, etc.)
2. Then I can answer specific questions accurately

Please share your relevant details with me, and I'll be happy to help!"""
    }
}


# -------- Core helpers --------

def new_session_bundle(locale: Locale = Locale.HE) -> SessionBundle:
    return SessionBundle(
        user_profile=UserProfile(),
        history=ConversationHistory(),
        phase=Phase.INFO_COLLECTION,
        locale=locale,
        request_id=None,
    )


async def post_chat(req: ChatRequest) -> ChatResponse:
    async with httpx.AsyncClient(timeout=60.0) as client:
        r = await client.post(
            f"{API_BASE}/chat",
            json=req.model_dump(),
            headers={"X-Request-ID": str(uuid.uuid4())},
        )
        r.raise_for_status()
        return ChatResponse.model_validate(r.json())


def _citation_target_exists(uri: str) -> bool:
    """Lightweight existence check: files via os.path, URLs assumed OK."""
    try:
        parsed = urllib.parse.urlparse(uri)
    except Exception:
        return False

    if parsed.scheme in ("http", "https"):
        return True
    if parsed.scheme == "file":
        return os.path.exists(parsed.path)
    return False


def enrich_text_with_citation_links(
    text: str,
    citations: List[str],
) -> Tuple[str, List[str]]:
    """
    Turns [d] into [d](uri) only when:
    - d is within citations range
    - target exists (for file://) or is http(s)
    Returns (new_text, used_citation_links).
    """
    if not citations:
        return text, []

    try:
        indices_in_text = {int(n) for n in re.findall(r"\[(\d+)\]", text)}
    except Exception as e:
        log.warning("Failed parsing citation indices: %s", e)
        return text, []

    used: List[Tuple[int, str]] = []

    for idx in sorted(indices_in_text):
        i = idx - 1
        if 0 <= i < len(citations):
            uri = citations[i]
            try:
                if _citation_target_exists(uri):
                    used.append((idx, uri))
                else:
                    log.info("Citation %d target invalid or missing: %r", idx, uri)
            except Exception as e:
                log.warning("Error checking citation %d (%r): %s", idx, uri, e)
        else:
            log.info("Citation index [%d] out of range", idx)

    idx_to_uri = {idx: uri for idx, uri in used}

    def repl(match: re.Match) -> str:
        idx = int(match.group(1))
        uri = idx_to_uri.get(idx)
        if not uri:
            return match.group(0)
        # Properly encode unsafe characters
        safe_uri = urllib.parse.quote(uri, safe="/:#?&=")
        return f"[{idx}]({safe_uri})"

    new_text = re.sub(r"\[(\d+)\]", repl, text)
    sources_lines = [f"[{idx}]({uri})" for idx, uri in used]
    return new_text, sources_lines


def header_html(lang: str) -> str:
    t = TRANSLATIONS[lang]
    return f"""
<div class="header-text">
<h1>{t['title']}</h1>
<h3>{t['subtitle']}</h3>
</div>
"""


# -------- Chat flow for Gradio --------

def add_user_message(
    message: str,
    history: List[List[str]],
    sb: SessionBundle,
    lang: str,   # kept for signature compatibility; not used currently
) -> Tuple[List[List[str]], str, SessionBundle]:
    if not message or not message.strip():
        return history, "", sb

    history = history + [[message, None]]
    sb.history.turns.append(Turn(user_text=message, assistant_text=None))
    if len(sb.history.turns) > MAX_TURNS:
        sb.history.turns = sb.history.turns[-MAX_TURNS:]

    return history, "", sb


async def fetch_assistant_reply(
    history: List[List[str]],
    sb: SessionBundle,
    lang: str,
) -> Tuple[List[List[str]], SessionBundle]:
    t = TRANSLATIONS[lang]

    if not history:
        return history, sb

    last_user_msg = history[-1][0]

    try:
        resp = await post_chat(ChatRequest(session_bundle=sb, user_input=last_user_msg))

        assistant_text, used_sources = enrich_text_with_citation_links(
            resp.assistant_text,
            resp.citations or [],
        )

        if used_sources:
            citations_block = "\n".join(f"• {line}" for line in used_sources)
            assistant_text += f"\n\n—\n**{t['sources']}:**\n{citations_block}"

        history[-1][1] = assistant_text

        sb.history.turns[-1].assistant_text = assistant_text
        sb.history.turns[-1].citations = resp.citations or []
        sb.user_profile = resp.user_profile
        sb.phase = resp.suggested_phase

        return history, sb

    except Exception as e:
        log.exception(f"Frontend error calling /chat: {e}", extra={"request_id": sb.request_id})
        user_msg = (
            f"{t['error']}: אירעה תקלה טכנית. נסה/י שוב מאוחר יותר."
            if lang == "he"
            else f"{t['error']}: A technical error occurred. Please try again later."
        )
        history[-1][1] = user_msg
        return history, sb



def change_language(lang: str):
    from gradio import update  # local import to avoid hard dep here
    from ..core_models import Locale as Loc

    t = TRANSLATIONS[lang]
    locale = Loc.HE if lang == "he" else Loc.EN
    new_sb = new_session_bundle(locale)

    return (
        header_html(lang),
        update(placeholder=t["placeholder"]),
        update(value=t["send"]),
        update(label=t["language"]),
        new_sb,
    )


async def initialize_session(sb: SessionBundle, lang: str) -> Tuple[List[List[str]], SessionBundle]:
    t = TRANSLATIONS[lang]
    return [[None, t["system_intro"]]], sb

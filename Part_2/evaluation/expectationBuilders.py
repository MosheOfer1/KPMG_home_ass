from __future__ import annotations

import re
from typing import Callable

from Part_2.core_models import (
    Phase, UserProfile, ChatResponse, Gender, HMO, Tier, Locale
)


# -------------------------------
# Helpers: profiles & expectations
# -------------------------------
def default_profile() -> UserProfile:
    return UserProfile(
        first_name="דוד",
        last_name="כהן",
        id_number="123456789",
        gender=Gender.MALE,
        birth_year=1988,
        hmo_name=HMO.MACCABI,
        hmo_card_number="987654321",
        membership_tier=Tier.GOLD,
        locale=Locale.HE,
    )

def with_overrides(p: UserProfile, **overrides) -> UserProfile:
    """Return a copy of p with dataclass-like field overrides (works with p.__dict__)."""
    d = p.__dict__.copy()
    d.update(overrides)
    return UserProfile(**d)

# --- Expectation builders (each returns a callable that asserts on the ChatResponse) ---

def expect_type_and_basics() -> Callable[[ChatResponse], None]:
    def _check(resp: ChatResponse) -> None:
        assert isinstance(resp, ChatResponse)
        assert isinstance(resp.user_profile, UserProfile)
        assert isinstance(resp.citations, list)
        assert isinstance(resp.validation_flags, list)
        assert resp.assistant_text and len(resp.assistant_text) > 5, "assistant_text too short/empty"
        assert resp.suggested_phase in {Phase.INFO_COLLECTION, Phase.QNA}
    return _check

def expect_words(*words: str) -> Callable[[ChatResponse], None]:
    def _check(resp: ChatResponse) -> None:
        text = resp.assistant_text
        for w in words:
            assert w in text, f"Expected word/phrase '{w}' in assistant_text"
    return _check

def expect_any_substring(*alts: str) -> Callable[[ChatResponse], None]:
    def _check(resp: ChatResponse) -> None:
        s = resp.assistant_text.replace(" ", "")
        assert any(a.replace(" ", "") in s for a in alts), f"Expected any of {alts}"
    return _check

def expect_percent_rough(value: int) -> Callable[[ChatResponse], None]:
    """
    Accepts numeric like '90%' or the Hebrew word for it. Add more forms if needed.
    """
    heb_map = {
        90: ["תשעים", "תשעיםאחוז", "תשעיםאחוזים"],
        80: ["שמונים", "שמוניםאחוז", "שמוניםאחוזים"],
    }
    def _check(resp: ChatResponse) -> None:
        t = resp.assistant_text
        normalized = t.replace(" ", "").replace("%", "")
        patterns = [str(value)]
        patterns += heb_map.get(value, [])
        assert any(p in normalized for p in patterns), f"Expected a ~{value}% mention; got: {t}"
    return _check

def expect_regex(pattern: str, flags: int = 0) -> Callable[[ChatResponse], None]:
    rx = re.compile(pattern, flags)
    def _check(resp: [ChatResponse]) -> None:
        assert rx.search(resp.assistant_text), f"Regex '{pattern}' not found in assistant_text"
    return _check

def expect_citations_are_files() -> Callable[[ChatResponse], None]:
    def _check(resp: [ChatResponse]) -> None:
        if resp.citations:
            assert all(str(u).startswith("file://") for u in resp.citations), "Citations should be KB URIs (file://...)"
    return _check
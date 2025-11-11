from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Sequence

import pytest

from Part_2.azure_integration import load_config
from Part_2.core_models import (
    SessionBundle, Locale, Phase, ChatRequest, ChatResponse,
    HMO, Tier
)
from Part_2.orchestrator.config import OrchestratorConfig
from Part_2.orchestrator.service import OrchestratorService
from Part_2.retriever.config import RetrieverConfig
from Part_2.evaluation.expectationBuilders import expect_type_and_basics, expect_words, expect_percent_rough, \
    expect_citations_are_files, expect_any_substring, default_profile, with_overrides


# -------------------------------
# Parametrized test cases
# -------------------------------

@dataclass
class Case:
    user_input: str
    profile_overrides: Dict = field(default_factory=dict)
    expectations: Sequence[Callable[[ChatResponse], None]] = field(default_factory=list)
    id: Optional[str] = None  # pytest id

# Add/modify cases here. Each case can tweak the profile and its own assertions.
CASES: List[Case] = [
    Case(
        id="preg-genetic-maccabi-gold",
        user_input="כמה אחוז הנחה יש לי בשביל בדיקות סקר גנטיות?",
        profile_overrides={"hmo_name": HMO.MACCABI, "membership_tier": Tier.GOLD, "locale": Locale.HE},
        expectations=[
            expect_type_and_basics(),
            expect_words("הנחה", "ייעוץ גנטי"),
            expect_percent_rough(90),
            expect_citations_are_files(),
        ],
    ),
    Case(
        id="preg-genetic-clalit-gold",
        user_input="מה הכיסוי בבדיקות סקר גנטיות?",
        profile_overrides={"hmo_name": HMO.CLALIT, "membership_tier": Tier.GOLD, "locale": Locale.HE},
        expectations=[
            expect_type_and_basics(),
            expect_any_substring("95", "תשעים וחמש"),
            expect_words("הנחה", "כיסוי"),
            expect_citations_are_files(),
        ],
    ),
    Case(
        id="preg-scan-silver-maccabi",
        user_input="מה מגיע לי בסקירות מערכות?",
        profile_overrides={"hmo_name": HMO.MACCABI, "membership_tier": Tier.SILVER},
        expectations=[
            expect_type_and_basics(),
            expect_words("סקירה", "חינם"),
            expect_citations_are_files(),
        ],
    ),
    Case(
        id="comm-dx-maccabi-gold",
        user_input="כמה משלמים על אבחון הפרעות שפה ודיבור?",
        profile_overrides={"hmo_name": HMO.MACCABI, "membership_tier": Tier.GOLD},
        expectations=[
            expect_type_and_basics(),
            expect_percent_rough(90),
            expect_words("דוח", "שפה", "דיבור"),
            expect_citations_are_files(),
        ],
    ),
    Case(
        id="comm-stutter-clalit-silver",
        user_input="מה ההטבה לטיפול בגמגום?",
        profile_overrides={"hmo_name": HMO.CLALIT, "membership_tier": Tier.SILVER},
        expectations=[
            expect_type_and_basics(),
            expect_percent_rough(65),
            expect_words("טיפול", "גמגום", "הנחה"),
            expect_citations_are_files(),
        ],
    ),
    Case(
        id="comm-dysphagia-meuhedet-gold",
        user_input="יש כיסוי לאבחון/טיפול בבליעה?",
        profile_overrides={"hmo_name": HMO.MEUHEDET, "membership_tier": Tier.GOLD},
        expectations=[
            expect_type_and_basics(),
            expect_percent_rough(80),
            expect_words("בליעה", "תזונתי"),
            expect_citations_are_files(),
        ],
    ),
    Case(
        id="dental-cleaning-maccabi-gold",
        user_input="ניקוי ובדיקת שיניים – מה מגיע לי?",
        profile_overrides={"hmo_name": HMO.MACCABI, "membership_tier": Tier.GOLD},
        expectations=[
            expect_type_and_basics(),
            expect_words("חינם", "פעמיים", "בדיקה"),
            expect_citations_are_files(),
        ],
    ),
    Case(
        id="dental-fillings-meuhedet-gold",
        user_input="מה ההנחה על סתימות?",
        profile_overrides={"hmo_name": HMO.MEUHEDET, "membership_tier": Tier.GOLD},
        expectations=[
            expect_type_and_basics(),
            expect_percent_rough(75),
            expect_words("סתימות", "חומרים"),
            expect_citations_are_files(),
        ],
    ),
    Case(
        id="dental-ortho-clalit-gold",
        user_input="יש השתתפות ביישור שיניים?",
        profile_overrides={"hmo_name": HMO.CLALIT, "membership_tier": Tier.GOLD},
        expectations=[
            expect_type_and_basics(),
            expect_percent_rough(40),
            expect_words("אורתודונטי", "שיניים"),
            expect_citations_are_files(),
        ],
    ),
    Case(
        id="opto-exam-clalit-gold",
        user_input="בדיקות ראייה – כמה זה עולה?",
        profile_overrides={"hmo_name": HMO.CLALIT, "membership_tier": Tier.GOLD},
        expectations=[
            expect_type_and_basics(),
            expect_words("בדיקה", "חינם", "ראייה"),
            expect_citations_are_files(),
        ],
    ),
    Case(
        id="opto-glasses-maccabi-gold",
        user_input="מה ההטבה למשקפי ראייה?",
        profile_overrides={"hmo_name": HMO.MACCABI, "membership_tier": Tier.GOLD},
        expectations=[
            expect_type_and_basics(),
            expect_percent_rough(70),
            expect_words("משקפיים", "שנתיים"),
            expect_citations_are_files(),
        ],
    ),
    Case(
        id="opto-contacts-clalit-gold",
        user_input="עדשות מגע – יש הנחה?",
        profile_overrides={"hmo_name": HMO.CLALIT, "membership_tier": Tier.GOLD},
        expectations=[
            expect_type_and_basics(),
            expect_percent_rough(65),
            expect_words("עדשות", "ניסיון"),
            expect_citations_are_files(),
        ],
    ),
    Case(
        id="alt-acupuncture-maccabi-gold",
        user_input="דיקור סיני – מה ההטבה?",
        profile_overrides={"hmo_name": HMO.MACCABI, "membership_tier": Tier.GOLD},
        expectations=[
            expect_type_and_basics(),
            expect_percent_rough(70),
            expect_words("דיקור", "טיפולים"),
            expect_citations_are_files(),
        ],
    ),
    Case(
        id="alt-chiro-clalit-gold",
        user_input="כירופרקטיקה – מה הכיסוי?",
        profile_overrides={"hmo_name": HMO.CLALIT, "membership_tier": Tier.GOLD},
        expectations=[
            expect_type_and_basics(),
            expect_percent_rough(85),
            expect_words("כירופרקטיקה", "טיפולים"),
            expect_citations_are_files(),
        ],
    ),
    Case(
        id="workshops-smoking-maccabi-gold",
        user_input="סדנת הפסקת עישון – כמה עולה?",
        profile_overrides={"hmo_name": HMO.MACCABI, "membership_tier": Tier.GOLD},
        expectations=[
            expect_type_and_basics(),
            expect_words("חינם", "עישון", "טיפול"),
            expect_citations_are_files(),
        ],
    ),
    Case(
        id="workshops-nutrition-silver-maccabi",
        user_input="סדנת תזונה – יש הנחה?",
        profile_overrides={"hmo_name": HMO.MACCABI, "membership_tier": Tier.SILVER},
        expectations=[
            expect_type_and_basics(),
            expect_percent_rough(70),
            expect_words("תזונה", "דיאטנית"),
            expect_citations_are_files(),
        ],
    ),
    Case(
        id="workshops-stress-meuhedet-gold",
        user_input="יש סדנאות לניהול מתח?",
        profile_overrides={"hmo_name": HMO.MEUHEDET, "membership_tier": Tier.GOLD},
        expectations=[
            expect_type_and_basics(),
            expect_words("חינם", "יוגה"),
            expect_citations_are_files(),
        ],
    ),
    Case(
        id="preg-course-clalit-gold",
        user_input="קורס הכנה ללידה – מה מגיע לי?",
        profile_overrides={"hmo_name": HMO.CLALIT, "membership_tier": Tier.GOLD},
        expectations=[
            expect_type_and_basics(),
            expect_words("חינם", "יועצת", "הנקה"),
            expect_citations_are_files(),
        ],
    ),
]


# ----------
# Fixtures
# ----------
@pytest.fixture(scope="module")
def cfgs():
    orch_cfg = OrchestratorConfig()
    aoai_cfg = load_config()
    ret_cfg = RetrieverConfig()
    return orch_cfg, aoai_cfg, ret_cfg


# ----------
# Test
# ----------
@pytest.mark.asyncio
@pytest.mark.parametrize("case", CASES, ids=lambda c: c.id or c.user_input[:30])
async def test_orchestrator_flexible_cases(cfgs, case: Case):
    orch_cfg, aoai_cfg, ret_cfg = cfgs
    svc = OrchestratorService(orch_cfg, aoai_cfg, ret_cfg)

    # Build profile for this case
    base = default_profile()
    prof = with_overrides(base, **case.profile_overrides)

    # Build session + request
    sb = SessionBundle(locale=prof.locale, phase=Phase.QNA, user_profile=prof)
    req = ChatRequest(user_input=case.user_input, session_bundle=sb)

    # Run orchestrator
    resp: ChatResponse = await svc.handle_chat(req, request_id="test")

    # Apply expectations
    for check in case.expectations:
        check(resp)

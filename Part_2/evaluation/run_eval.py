from __future__ import annotations

import argparse
import asyncio
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence

import matplotlib.pyplot as plt
import pandas as pd

# -----------------------------
# Inline expectation builders
# -----------------------------
# Use exactly these; do NOT import from elsewhere.
from .expectationBuilders import expect_type_and_basics, expect_any_substring, \
    expect_percent_rough, expect_regex, expect_citations_are_files, expect_words

_EXPECTATION_REGISTRY: Dict[str, Callable[..., Callable[[ChatResponse], None]]] = {
    "expect_type_and_basics": expect_type_and_basics,
    "expect_any_substring": expect_any_substring,
    "expect_percent_rough": expect_percent_rough,
    "expect_regex": expect_regex,
    "expect_citations_are_files": expect_citations_are_files,
    "expect_words": expect_words,
}

# -----------------------------
# Project imports
# -----------------------------
from ..core_models import (
    SessionBundle, Locale, Phase, ChatRequest, ChatResponse,
    HMO, Tier, Gender, UserProfile
)
from ..orchestrator.config import OrchestratorConfig
from ..orchestrator.service import OrchestratorService
from ..retriever.config import RetrieverConfig
from ..azure_integration import load_config

# -----------------------------
# Data models / helpers
# -----------------------------
@dataclass
class Case:
    user_input: str
    profile_overrides: Dict[str, Any]
    expectations: Sequence[Callable[[ChatResponse], None]]
    id: Optional[str] = None

_ENUM_MAP = {
    "hmo_name": HMO,
    "membership_tier": Tier,
    "gender": Gender,
    "locale": Locale,
}

def _coerce_enums(d: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(d or {})
    for k, enum in _ENUM_MAP.items():
        v = out.get(k, None)
        if isinstance(v, str):
            out[k] = enum[v.upper()]
    return out

def _build_expectations(specs: Sequence[Dict[str, Any]]) -> List[Callable[[ChatResponse], None]]:
    exps = []
    for s in specs or []:
        name = s["fn"]
        fn = _EXPECTATION_REGISTRY[name]
        args = s.get("args", [])
        kwargs = s.get("kwargs", {})
        exps.append(fn(*args, **kwargs))
    return exps

def _load_cases(path: Path) -> List[Case]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    items: List[Case] = []
    for item in data:
        expectations = _build_expectations(item.get("expectations", []))
        overrides = _coerce_enums(item.get("profile_overrides", {}))
        items.append(Case(
            id=item.get("id"),
            user_input=item["user_input"],
            profile_overrides=overrides,
            expectations=expectations
        ))
    return items

# -----------------------------
# Runner
# -----------------------------
async def _run_case(svc: OrchestratorService, case: Case) -> Dict[str, Any]:
    # default_profile & with_overrides are simple; keep it inline to avoid importing tests
    base = UserProfile(
        first_name="Israel",
        last_name="Israeli",
        id_number="123456789",
        gender=Gender.MALE,
        birth_year=1990,
        hmo_name=HMO.MACCABI,
        hmo_card_number="987654321",
        membership_tier=Tier.GOLD,
    )
    for k, v in case.profile_overrides.items():
        setattr(base, k, v)

    sb = SessionBundle(phase=Phase.QNA, user_profile=base)
    req = ChatRequest(user_input=case.user_input, session_bundle=sb)

    t0 = time.perf_counter()
    resp: ChatResponse = await svc.handle_chat(req, request_id=case.id or "eval")
    dt = time.perf_counter() - t0

    ok, err = True, ""
    try:
        for check in case.expectations:
            check(resp)
    except AssertionError as e:
        ok, err = False, str(e)

    return {
        "id": case.id or case.user_input[:40],
        "user_input": case.user_input,
        "passed": ok,
        "error": err,
        "latency_sec": round(dt, 3),
        "suggested_phase": getattr(resp, "suggested_phase", None),
        "citations_count": len(getattr(resp, "citations", []) or []),
    }


# -----------------------------
# Main evaluation runner
# -----------------------------
async def main():
    ap = argparse.ArgumentParser(description="Evaluation runner for Orchestrator+Retriever")
    ap.add_argument("--cases", type=Path, required=True, help="Path to cases.json")
    ap.add_argument("--outdir", type=Path, default=Path("Part_2/evaluation/eval_out"), help="Output directory")
    args = ap.parse_args()

    cases = _load_cases(args.cases)

    orch_cfg = OrchestratorConfig()
    aoai_cfg = load_config()
    ret_cfg = RetrieverConfig()
    svc = OrchestratorService(orch_cfg, aoai_cfg, ret_cfg)

    results: List[Dict[str, Any]] = []
    for c in cases:
        results.append(await _run_case(svc, c))

    args.outdir.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(results).sort_values(by="id")
    df.to_csv(args.outdir / "eval_results.csv", index=False)

    # -----------------------------
    # Plots
    # -----------------------------
    # 1) Latency
    plt.figure()
    ax1 = df.plot(kind="bar", x="id", y="latency_sec", legend=False, rot=45, figsize=(10, 5),
                  title="Latency per Case (seconds)")
    ax1.set_xlabel("Case")
    ax1.set_ylabel("Seconds")
    plt.tight_layout()
    plt.savefig(args.outdir / "latency.png", dpi=150)

    # 2) Pass/Fail per Case (bars)
    plt.figure()
    df["pass_numeric"] = df["passed"].astype(int)
    ax2 = df.plot(kind="bar", x="id", y="pass_numeric", legend=False, rot=45, figsize=(10, 5),
                  title="Result per Case (1=pass, 0=fail)")
    ax2.set_xlabel("Case")
    ax2.set_ylabel("Pass=1 / Fail=0")
    ax2.set_ylim(0, 1.1)
    plt.tight_layout()
    plt.savefig(args.outdir / "results_bar.png", dpi=150)

    # 3) Pie chart (True vs False)
    plt.figure()
    counts = df["passed"].value_counts()
    plt.pie(
        counts,
        labels=["Passed", "Failed"],
        autopct="%1.1f%%",
        colors=["#4CAF50", "#F44336"],
        startangle=90
    )
    plt.title("Overall Evaluation Results")
    plt.savefig(args.outdir / "results_pie.png", dpi=150)

    # -----------------------------
    # Summary
    # -----------------------------
    total = len(df)
    passed = int(df["passed"].sum())
    print(f"✔ Passed {passed}/{total}")
    print(f"Wrote CSV and plots to: {args.outdir}")

if __name__ == "__main__":
    asyncio.run(main())

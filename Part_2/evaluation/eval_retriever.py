from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import List, Dict, Any

import pandas as pd
import matplotlib.pyplot as plt

from ..core_models import HMO, Tier
from ..azure_integration import load_config, AzureEmbeddingsClient
from ..retriever.config import RetrieverConfig
from ..retriever.kb import HtmlKB

@dataclass
class RetrieverCase:
    """
    Represents a single test case for a retriever system.

    This class is used to encapsulate all relevant information about a retriever
    test case, including its identifier, input query, associated health
    maintenance organization (HMO) data or retrieval tier, and the expected
    retrieved URIs.

    Attributes:
        id: str
            A unique identifier for the test case.
        query: str
            The input query corresponding to the test case.
        hmo: HMO | None
            The HMO data associated with the test case, if applicable.
        tier: Tier | None
            The tier level associated with the test case, if applicable.
        expected_uris: List[str]
            A list of URIs expected to be retrieved for this test case.
    """
    id: str
    query: str
    hmo: HMO | None
    tier: Tier | None
    expected_uris: List[str]

def load_cases(path: Path) -> List[RetrieverCase]:
    data: List[Dict[str, Any]] = json.loads(path.read_text(encoding="utf-8"))
    out: List[RetrieverCase] = []
    for row in data:
        out.append(
            RetrieverCase(
                id=row["id"],
                query=row["query"],
                hmo=HMO[row["hmo"]] if row.get("hmo") else None,
                tier=Tier[row["tier"]] if row.get("tier") else None,
                expected_uris=[r.split("#")[-1] for r in row["expected_uris"]],
            )
        )
    return out

def main(cases_path: str, top_k: int = 1):
    cases = load_cases(Path(cases_path))
    ret_cfg = RetrieverConfig()
    aoai_cfg = load_config()
    embedder = AzureEmbeddingsClient(aoai_cfg, default_deployment=ret_cfg.embeddings_deployment)
    kb = HtmlKB(ret_cfg.kb_dir, embedder, cache_dir=ret_cfg.cache_dir)

    rows = []
    for c in cases:
        found = kb.search(c.query, hmo=c.hmo, tier=c.tier, top_k=top_k)
        uris = [ch.source_uri.split("#")[-1] for ch in found]

        hits = [u for u in uris if u in c.expected_uris]
        hit_at_k = int(len(hits) > 0)
        rank = min((uris.index(u) + 1 for u in hits), default=None)
        mrr = 0.0 if rank is None else 1.0 / rank

        rows.append({
            "id": c.id,
            "hit_at_k": hit_at_k,
            "mrr": mrr,
            "retrieved_uris": ";".join(uris),
            "expected_uris": ";".join(c.expected_uris),
        })

    df = pd.DataFrame(rows)
    outdir = Path("Part_2/evaluation/eval_out")
    outdir.mkdir(parents=True, exist_ok=True)
    df.to_csv(outdir / "retriever_eval.csv", index=False)
    print(df[["id", "hit_at_k", "mrr"]])

    # Pie chart: pass/fail distribution
    counts = df["hit_at_k"].value_counts().to_dict()
    labels = ["Hit@K = 1", "Hit@K = 0"]
    sizes = [counts.get(1, 0), counts.get(0, 0)]

    plt.figure(figsize=(5, 5))
    plt.pie(sizes, labels=labels, autopct='%1.1f%%', startangle=140)
    plt.title("Retriever Hit@K Distribution")

    plt.savefig(outdir / "retriever_pie.png", dpi=120, bbox_inches="tight")
    plt.close()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--cases", type=str, required=True)
    args = ap.parse_args()
    main(args.cases)

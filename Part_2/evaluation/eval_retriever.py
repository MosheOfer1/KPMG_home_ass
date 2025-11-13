from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import List, Dict, Any

import pandas as pd

from ..core_models import HMO, Tier
from ..azure_integration import load_config, AzureEmbeddingsClient
from ..retriever.config import RetrieverConfig
from ..retriever.kb import HtmlKB

@dataclass
class RetrieverCase:
    id: str
    query: str
    hmo: HMO | None
    tier: Tier | None
    expected_uris: List[str]

def load_cases(path: Path) -> List[RetrieverCase]:
    data: List[Dict[str, Any]] = json.loads(path.read_text())
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

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--cases", type=str, required=True)
    args = ap.parse_args()
    main(args.cases)

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
eval_dataset.py
A minimal, elegant evaluator for (pdf, golden.json) pairs.
- Reuses predictions in --pred-dir if present, else calls main.run(...)
- Metrics: per-field accuracy & avg similarity, overall exact match rate
- Outputs: per_example.csv, per_field.csv, summary.json, 2 bar plots
"""

from __future__ import annotations

import argparse
import csv
import difflib
import json
import logging
from pathlib import Path
from typing import Any, Dict, List

import matplotlib.pyplot as plt
from tqdm import tqdm

from Part_1.main import run

# --- logging ---
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger("eval")

# --- schema bits (kept tiny) ---
DATE_KEYS = ["day", "month", "year"]
ADDRESS_KEYS = ["street","houseNumber","entrance","apartment","city","postalCode"]
SCALARS = ["lastName","firstName","idNumber","gender","landlinePhone","mobilePhone","timeOfInjury",
           "accidentLocation","accidentDescription","accidentAddress","injuredBodyPart","signature",
           "healthFundMember","natureOfAccident"]
DATES = ["dateOfBirth","dateOfInjury","formFillingDate","formReceiptDateAtClinic"]
ADDR = "address"

# --- tiny utils ---
norm = lambda x: " ".join(str(x or "").split())
digits = lambda s: "".join(ch for ch in norm(s) if ch.isdigit())
sim = lambda a,b: difflib.SequenceMatcher(a=norm(a), b=norm(b)).ratio()

def cmp_scalar(k,g,p):
    if k in {"landlinePhone","mobilePhone","idNumber"}:
        G,P = digits(g), digits(p); return (G==P), sim(G,P), G, P
    G,P = norm(g), norm(p);         return (G==P), sim(G,P), G, P

def as_int(x):
    try: return int(str(x))
    except: return -10**9

def cmp_date(g,p):
    G = {k: as_int((g or {}).get(k)) for k in DATE_KEYS}
    P = {k: as_int((p or {}).get(k)) for k in DATE_KEYS}
    eq = all(G[k]==P[k] for k in DATE_KEYS)
    s = sum(G[k]==P[k] for k in DATE_KEYS)/len(DATE_KEYS)
    return eq, s, G, P

def cmp_addr(g,p):
    G = {k: norm((g or {}).get(k,"")) for k in ADDRESS_KEYS}
    P = {k: norm((p or {}).get(k,"")) for k in ADDRESS_KEYS}
    eq = all(G[k]==P[k] for k in ADDRESS_KEYS)
    s = sum(sim(G[k],P[k]) for k in ADDRESS_KEYS)/len(ADDRESS_KEYS)
    return eq, s, G, P

# --- plotting (1 fig per chart, no custom colors) ---
def bar_plot(labels, values, title, out_png):
    plt.figure()
    plt.bar(range(len(labels)), values)
    plt.xticks(range(len(labels)), labels, rotation=90)
    plt.ylim(0,1)
    plt.title(title); plt.xlabel("Field"); plt.ylabel("Score")
    plt.tight_layout()
    Path(out_png).parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(out_png, dpi=150); plt.close()

# --- core ---

def predict_if_needed(pdf_path: Path, out_json: Path, hebrew: bool, di_model: str|None):
    out_json.parent.mkdir(parents=True, exist_ok=True)
    if not out_json.exists():
        run(str(pdf_path), str(out_json), hebrew, di_model, None)

def eval_one(gold: Dict[str,Any], pred: Dict[str,Any]):
    rec = {}
    for k in SCALARS:
        eq,s,G,P = cmp_scalar(k, gold.get(k,""), pred.get(k,""))
        rec[k] = {"equal":eq,"sim":s,"gold":G,"pred":P}
    for k in DATES:
        eq,s,G,P = cmp_date(gold.get(k,{}), pred.get(k,{}))
        rec[k] = {"equal":eq,"sim":s,"gold":G,"pred":P}
    eq,s,G,P = cmp_addr(gold.get(ADDR,{}), pred.get(ADDR,{}))
    rec[ADDR] = {"equal":eq,"sim":s,"gold":G,"pred":P}
    rec["_full_em"] = all(v["equal"] for v in rec.values())
    return rec

def aggregate(all_recs: List[Dict[str,Any]]):
    fields = [f for f in all_recs[0].keys() if f!="_full_em"] if all_recs else []
    agg = {f: {"n":0,"correct":0,"sim":0.0} for f in fields}
    for r in all_recs:
        for f in fields:
            agg[f]["n"] += 1
            agg[f]["correct"] += int(r[f]["equal"])
            agg[f]["sim"] += float(r[f]["sim"])
    for f in fields:
        n = max(agg[f]["n"],1)
        agg[f]["acc"] = agg[f]["correct"]/n
        agg[f]["sim"] = agg[f]["sim"]/n
    overall = {
        "n_examples": len(all_recs),
        "full_exact_match_rate": sum(int(r["_full_em"]) for r in all_recs)/max(len(all_recs),1)
    }
    return agg, overall, fields

def write_csv(path: Path, rows: List[Dict[str,Any]], fieldnames: List[str]):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path,"w",encoding="utf-8",newline="") as f:
        w=csv.DictWriter(f, fieldnames=fieldnames); w.writeheader(); w.writerows(rows)

def main():
    ap = argparse.ArgumentParser(description="Evaluate dataset with tqdm + logs.")
    ap.add_argument("--dataset", required=True, help="Folder with *.pdf + *.golden.json")
    ap.add_argument("--outdir", required=True, help="Where to write reports/plots")
    ap.add_argument("--pred-dir", default=None, help="Reuse/store predictions here")
    ap.add_argument("--hebrew", action="store_true", help="Pass Hebrew flag to extractor")
    ap.add_argument("--di-model", default=None, help="Optional DI model id")
    args = ap.parse_args()

    ds = Path(args.dataset); outdir = Path(args.outdir)
    pred_dir = Path(args.pred_dir) if args.pred_dir else (outdir / "pred")
    pairs = [(p.stem, p, ds/f"{p.stem}.golden.json") for p in sorted(ds.glob("*.pdf")) if (ds/f"{p.stem}.golden.json").exists()]
    if not pairs: log.error("No (pdf, golden.json) pairs found."); return

    per_example, all_recs = [], []

    log.info("Evaluating %d examples…", len(pairs))
    for stem, pdf_path, g_path in tqdm(pairs, desc="Evaluating", unit="ex"):
        pred_path = pred_dir/f"{stem}.pred.json"
        predict_if_needed(pdf_path, pred_path, args.hebrew, args.di_model)
        gold = json.loads(Path(g_path).read_text(encoding="utf-8"))
        pred = json.loads(Path(pred_path).read_text(encoding="utf-8"))
        rec = eval_one(gold, pred); all_recs.append(rec)
        row = {"stem":stem, "full_exact_match": int(rec["_full_em"])}
        for f,info in rec.items():
            if f=="_full_em": continue
            row[f"{f}__equal"] = int(info["equal"])
            row[f"{f}__sim"]   = round(float(info["sim"]),4)
        per_example.append(row)

    agg, overall, fields = aggregate(all_recs)
    log.info("Full EM rate: %.3f over %d examples", overall["full_exact_match_rate"], overall["n_examples"])

    # outputs
    (outdir).mkdir(parents=True, exist_ok=True)
    # per-example
    ex_fields = ["stem","full_exact_match"] + [f"{f}__equal" for f in fields] + [f"{f}__sim" for f in fields]
    write_csv(outdir/"per_example.csv", per_example, ex_fields)
    # per-field
    pf_rows = [{"field":f,"n":agg[f]["n"],"correct":agg[f]["correct"],
                "accuracy":round(agg[f]["acc"],4),"avg_similarity":round(agg[f]["sim"],4)} for f in fields]
    write_csv(outdir/"per_field.csv", pf_rows, ["field","n","correct","accuracy","avg_similarity"])
    # summary
    Path(outdir/"summary.json").write_text(json.dumps({"per_field":pf_rows,"overall":overall}, ensure_ascii=False, indent=2), encoding="utf-8")

    # plots
    bar_plot([r["field"] for r in pf_rows], [r["accuracy"] for r in pf_rows], "Accuracy per field", outdir/"plot_accuracy_per_field.png")
    bar_plot([r["field"] for r in pf_rows], [r["avg_similarity"] for r in pf_rows], "Avg similarity per field", outdir/"plot_similarity_per_field.png")

    log.info("Saved reports/plots to: %s", outdir.resolve())

if __name__ == "__main__":
    main()

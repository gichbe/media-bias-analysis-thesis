from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd
from scipy.stats import hypergeom

from common import q, write_csv

def as_bool(value):
    return str(value).strip().lower() in {"true", "1", "yes", "da"}

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--selection", type=Path, default=Path("data/article_selection/selection_scores.csv"))
    parser.add_argument("--output-dir", type=Path, default=Path("results/article_selection"))
    args = parser.parse_args()

    args.output_dir.mkdir(parents=True, exist_ok=True)
    table = pd.read_csv(args.selection)
    required = {"suitability_score", "selected", "manual_reference"}
    missing = required - set(table.columns)
    if missing:
        raise RuntimeError(f"Selection file missing columns {sorted(missing)}")
    if "status" in table.columns:
        table = table[table["status"].astype(str).str.lower().eq("ok")].copy()
    table["selected"] = table["selected"].map(as_bool)
    table["manual_reference"] = table["manual_reference"].map(as_bool)
    n = len(table)
    selected_n = int(table["selected"].sum())
    manual = table[table["manual_reference"]]
    manual_n = len(manual)
    recovered = int(manual["selected"].sum())
    selection_rate = selected_n / n
    recovery_rate = recovered / manual_n
    expected = manual_n * selection_rate
    enrichment = recovery_rate / selection_rate
    p_value = float(hypergeom.sf(recovered - 1, n, manual_n, selected_n))
    score_all = table["suitability_score"].value_counts().sort_index()
    score_manual = manual["suitability_score"].value_counts().sort_index()

    write_csv(args.output_dir / "selection_summary.csv", [{
        "analyzed_n": n,
        "selected_n": selected_n,
        "selected_pct": q(selection_rate * 100, 2),
        "manual_reference_n": manual_n,
        "manual_recovered_n": recovered,
        "manual_recovered_pct": q(recovery_rate * 100, 2),
        "expected_random_overlap": q(expected, 2),
        "enrichment_factor": q(enrichment, 2),
        "hypergeometric_p": p_value,
    }])
    rows = []
    for score in sorted(set(score_all.index) | set(score_manual.index)):
        rows.append({
            "score": score,
            "all_n": int(score_all.get(score, 0)),
            "manual_reference_n": int(score_manual.get(score, 0)),
            "manual_reference_pct": q(score_manual.get(score, 0) / manual_n * 100, 2),
        })
    write_csv(args.output_dir / "score_distribution.csv", rows)

if __name__ == "__main__":
    main()

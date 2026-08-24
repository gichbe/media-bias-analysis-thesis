from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
from scipy.stats import rankdata, wilcoxon

from common import (
    DIMS,
    build_human_reference,
    holm_adjust,
    load_humans,
    load_models,
    model_common_ids,
    norm_val,
    q,
    write_csv,
)

def rank_biserial(diff):
    diff = np.asarray(diff, dtype=int)
    nonzero = diff[diff != 0]
    if len(nonzero) == 0:
        return 0.0
    ranks = rankdata(np.abs(nonzero), method="average")
    positive = float(ranks[nonzero > 0].sum())
    negative = float(ranks[nonzero < 0].sum())
    denom = positive + negative
    return (positive - negative) / denom if denom else 0.0

def consensus_macro(indices, model_names, models, refs, consensus, common_ids):
    values3 = []
    values2 = []
    for model_name in model_names:
        table = models[model_name]
        dim3 = []
        dim2 = []
        sampled = [common_ids[i] for i in indices]
        for dim in DIMS:
            for level, target in ((3, dim3), (2, dim2)):
                ids = [
                    aid
                    for aid in sampled
                    if refs[dim][aid] is not None and consensus[dim][aid] == level
                ]
                if not ids:
                    continue
                target.append(np.mean([
                    norm_val(table.loc[aid, dim], dim) == refs[dim][aid]
                    for aid in ids
                ]))
        values3.append(np.mean(dim3))
        values2.append(np.mean(dim2))
    a3 = float(np.mean(values3))
    a2 = float(np.mean(values2))
    return a3, a2, a3 - a2

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--human-dir", type=Path, default=Path("data/annotations/human"))
    parser.add_argument("--model-dir", type=Path, default=Path("data/annotations/models"))
    parser.add_argument("--model-manifest", type=Path, default=Path("analysis/models.csv"))
    parser.add_argument("--output-dir", type=Path, default=Path("results/statistics"))
    parser.add_argument("--bootstrap", type=int, default=2000)
    parser.add_argument("--seed", type=int, default=20260814)
    args = parser.parse_args()

    args.output_dir.mkdir(parents=True, exist_ok=True)
    humans, human_ids = load_humans(args.human_dir)
    _, model_list = load_models(args.model_dir, args.model_manifest)
    refs, consensus, _ = build_human_reference(humans, human_ids)
    common_ids = model_common_ids(human_ids, model_list)
    if len(common_ids) != 403:
        raise RuntimeError(f"Expected common set 403, got {len(common_ids)}")
    models = dict(model_list)
    model_names = [name for name, _ in model_list]

    human_tone = np.asarray([refs["tone"][aid] for aid in common_ids], dtype=int)
    human_abs = np.abs(human_tone)
    rows = []
    raw_p = []
    for name in model_names:
        model_tone = np.asarray([
            norm_val(models[name].loc[aid, "tone"], "tone")
            for aid in common_ids
        ], dtype=int)
        model_abs = np.abs(model_tone)
        diff = model_abs - human_abs
        if np.all(diff == 0):
            w, p = 0.0, 1.0
        else:
            result = wilcoxon(
                diff,
                zero_method="wilcox",
                correction=False,
                alternative="two-sided",
                method="auto",
            )
            w, p = float(result.statistic), float(result.pvalue)
        raw_p.append(p)
        rows.append({
            "model": name,
            "n": len(diff),
            "human_mean_abs_tone": q(human_abs.mean(), 6),
            "model_mean_abs_tone": q(model_abs.mean(), 6),
            "mean_difference": q(diff.mean(), 6),
            "median_difference": q(np.median(diff), 6),
            "lower_intensity_n": int(np.sum(diff < 0)),
            "equal_intensity_n": int(np.sum(diff == 0)),
            "higher_intensity_n": int(np.sum(diff > 0)),
            "wilcoxon_w": q(w, 6),
            "p_raw": p,
            "rank_biserial": q(rank_biserial(diff), 6),
        })
    adjusted = holm_adjust(raw_p)
    for row, p in zip(rows, adjusted):
        row["p_holm"] = p
        row["significant_holm_0_05"] = bool(p < 0.05)
    write_csv(args.output_dir / "wilcoxon_tone_intensity.csv", rows)

    observed = np.arange(len(common_ids))
    obs3, obs2, gap = consensus_macro(observed, model_names, models, refs, consensus, common_ids)
    rng = np.random.default_rng(args.seed)
    gaps = np.empty(args.bootstrap, dtype=float)
    for i in range(args.bootstrap):
        idx = rng.integers(0, len(common_ids), size=len(common_ids))
        gaps[i] = consensus_macro(idx, model_names, models, refs, consensus, common_ids)[2]
    low, high = np.quantile(gaps, [0.025, 0.975])
    write_csv(args.output_dir / "consensus_gap_bootstrap_summary.csv", [{
        "n": len(common_ids),
        "models": len(model_names),
        "agreement_3of3_pct": q(obs3 * 100, 4),
        "agreement_2of3_pct": q(obs2 * 100, 4),
        "gap_percentage_points": q(gap * 100, 4),
        "ci95_low_pp": q(low * 100, 4),
        "ci95_high_pp": q(high * 100, 4),
        "bootstrap_replicates": args.bootstrap,
        "seed": args.seed,
    }])

if __name__ == "__main__":
    main()

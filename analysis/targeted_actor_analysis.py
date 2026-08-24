from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
from sklearn.metrics import mean_absolute_error

from common import (
    TONE_ORDER,
    build_human_reference,
    krippendorff_alpha_ordinal,
    load_humans,
    load_models,
    model_common_ids,
    norm_val,
    q,
    safe_kappa,
    write_csv,
)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--human-dir", type=Path, default=Path("data/annotations/human"))
    parser.add_argument("--model-dir", type=Path, default=Path("data/annotations/models"))
    parser.add_argument("--model-manifest", type=Path, default=Path("analysis/models.csv"))
    parser.add_argument("--output-dir", type=Path, default=Path("results/targeted_actor"))
    args = parser.parse_args()

    args.output_dir.mkdir(parents=True, exist_ok=True)
    humans, human_ids = load_humans(args.human_dir)
    _, models = load_models(args.model_dir, args.model_manifest)
    refs, consensus, ratings = build_human_reference(humans, human_ids)
    common_ids = model_common_ids(human_ids, models)

    all_tone_items = [ratings["tone"][aid] for aid in human_ids]
    same_human_ids = [
        aid
        for aid in human_ids
        if len(set(ratings["dominant_actor"][aid])) == 1
    ]
    same_common_ids = [aid for aid in common_ids if aid in set(same_human_ids)]
    same_tone_items = [ratings["tone"][aid] for aid in same_human_ids]
    alpha_all = krippendorff_alpha_ordinal(all_tone_items, TONE_ORDER)
    alpha_same = krippendorff_alpha_ordinal(same_tone_items, TONE_ORDER)
    exact_all = float(np.mean([
        len(set(ratings["tone"][aid])) == 1
        for aid in human_ids
    ]))
    exact_same = float(np.mean([
        len(set(ratings["tone"][aid])) == 1
        for aid in same_human_ids
    ]))
    max_diff_le1 = float(np.mean([
        max(ratings["tone"][aid]) - min(ratings["tone"][aid]) <= 1
        for aid in human_ids
    ]))
    write_csv(args.output_dir / "human_tone_actor_alignment.csv", [{
        "full_n": len(human_ids),
        "same_actor_n": len(same_human_ids),
        "same_actor_common_n": len(same_common_ids),
        "alpha_full": q(alpha_all),
        "alpha_same_actor": q(alpha_same),
        "exact_full_pct": q(exact_all * 100, 2),
        "exact_same_actor_pct": q(exact_same * 100, 2),
        "max_human_tone_difference_at_most_1_pct": q(max_diff_le1 * 100, 2),
    }])

    rows = []
    for name, table in models:
        all_ids = [aid for aid in common_ids if refs["tone"][aid] is not None]
        y_all = [refs["tone"][aid] for aid in all_ids]
        p_all = [norm_val(table.loc[aid, "tone"], "tone") for aid in all_ids]
        target_ids = [
            aid
            for aid in same_common_ids
            if norm_val(table.loc[aid, "dominant_actor"], "dominant_actor")
            == ratings["dominant_actor"][aid][0]
        ]
        y = [refs["tone"][aid] for aid in target_ids]
        p = [norm_val(table.loc[aid, "tone"], "tone") for aid in target_ids]
        rows.append({
            "model": name,
            "n": len(target_ids),
            "weighted_kappa_all": q(safe_kappa(y_all, p_all, True)),
            "weighted_kappa_same_actor": q(safe_kappa(y, p, True)),
            "exact_same_actor_pct": q(np.mean(np.asarray(y) == np.asarray(p)) * 100, 2),
            "mae_same_actor": q(mean_absolute_error(y, p)),
            "human_neutral_same_actor_pct": q(np.mean(np.asarray(y) == 0) * 100, 2),
            "model_neutral_same_actor_pct": q(np.mean(np.asarray(p) == 0) * 100, 2),
            "human_mean_abs_tone_same_actor": q(np.mean(np.abs(y))),
            "model_mean_abs_tone_same_actor": q(np.mean(np.abs(p))),
        })
    rows.sort(key=lambda row: float(row["weighted_kappa_all"]), reverse=True)
    write_csv(args.output_dir / "targeted_actor_model_metrics.csv", rows)
    write_csv(args.output_dir / "targeted_actor_summary.csv", [{
        "models": len(rows),
        "avg_weighted_kappa_all": q(np.mean([float(row["weighted_kappa_all"]) for row in rows])),
        "avg_weighted_kappa_same_actor": q(np.mean([float(row["weighted_kappa_same_actor"]) for row in rows])),
        "avg_exact_all_pct": q(np.mean([
            np.mean([
                refs["tone"][aid] == norm_val(table.loc[aid, "tone"], "tone")
                for aid in common_ids
            ]) * 100
            for _, table in models
        ]), 2),
        "avg_exact_same_actor_pct": q(np.mean([float(row["exact_same_actor_pct"]) for row in rows]), 2),
        "avg_human_neutral_same_actor_pct": q(np.mean([float(row["human_neutral_same_actor_pct"]) for row in rows]), 2),
        "avg_model_neutral_same_actor_pct": q(np.mean([float(row["model_neutral_same_actor_pct"]) for row in rows]), 2),
        "avg_human_mean_abs_tone_same_actor": q(np.mean([float(row["human_mean_abs_tone_same_actor"]) for row in rows])),
        "avg_model_mean_abs_tone_same_actor": q(np.mean([float(row["model_mean_abs_tone_same_actor"]) for row in rows])),
        "models_with_lower_abs_tone_same_actor": sum(
            float(row["model_mean_abs_tone_same_actor"]) < float(row["human_mean_abs_tone_same_actor"])
            for row in rows
        ),
    }])

if __name__ == "__main__":
    main()

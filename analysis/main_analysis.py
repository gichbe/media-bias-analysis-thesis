from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path

import numpy as np
from scipy.stats import spearmanr
from sklearn.metrics import mean_absolute_error

from common import (
    BALANCE_ORDER,
    DIMS,
    DIM_LABELS,
    FRAME_CATS,
    HUMAN_FILES,
    LEAN_CATS,
    TONE_ORDER,
    build_human_reference,
    krippendorff_alpha_nominal,
    krippendorff_alpha_ordinal,
    load_humans,
    load_models,
    model_common_ids,
    norm_val,
    percentile_ci,
    portal_aliases,
    q,
    safe_kappa,
    write_csv,
)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--human-dir", type=Path, default=Path("data/annotations/human"))
    parser.add_argument("--model-dir", type=Path, default=Path("data/annotations/models"))
    parser.add_argument("--model-manifest", type=Path, default=Path("analysis/models.csv"))
    parser.add_argument("--output-dir", type=Path, default=Path("results/main"))
    parser.add_argument("--bootstrap", type=int, default=2000)
    parser.add_argument("--seed", type=int, default=20260814)
    args = parser.parse_args()

    args.output_dir.mkdir(parents=True, exist_ok=True)
    humans, human_ids = load_humans(args.human_dir)
    if len(human_ids) != 458:
        raise RuntimeError(f"Expected 458 human articles, got {len(human_ids)}")
    manifest, models = load_models(args.model_dir, args.model_manifest)
    if len(models) != 17:
        raise RuntimeError(f"Expected 17 models, got {len(models)}")
    refs, consensus, ratings = build_human_reference(humans, human_ids)
    rng = np.random.default_rng(args.seed)

    agreement_rows = []
    consensus_rows = []
    for dim in DIMS:
        items = [ratings[dim][aid] for aid in human_ids]
        if dim == "tone":
            alpha = krippendorff_alpha_ordinal(items, TONE_ORDER)
        elif dim == "balance":
            alpha = krippendorff_alpha_ordinal(items, BALANCE_ORDER)
        else:
            alpha = krippendorff_alpha_nominal(items)
        boots = []
        for _ in range(args.bootstrap):
            idx = rng.integers(0, len(items), size=len(items))
            sample = [items[i] for i in idx]
            if dim == "tone":
                boots.append(krippendorff_alpha_ordinal(sample, TONE_ORDER))
            elif dim == "balance":
                boots.append(krippendorff_alpha_ordinal(sample, BALANCE_ORDER))
            else:
                boots.append(krippendorff_alpha_nominal(sample))
        low, high = percentile_ci(boots)
        pairwise = []
        exact = []
        for a, b in ((0, 1), (0, 2), (1, 2)):
            y = [row[a] for row in items]
            p = [row[b] for row in items]
            pairwise.append(safe_kappa(y, p, dim in ("tone", "balance")))
            exact.append(float(np.mean(np.asarray(y, dtype=object) == np.asarray(p, dtype=object))))
        agreement_rows.append({
            "dimension": dim,
            "dimension_label": DIM_LABELS[dim],
            "krippendorff_alpha": q(alpha),
            "alpha_ci95_low": q(low),
            "alpha_ci95_high": q(high),
            "avg_pairwise_kappa": q(np.nanmean(pairwise)),
            "avg_pairwise_exact_pct": q(np.mean(exact) * 100, 2),
        })
        counts = Counter(consensus[dim][aid] for aid in human_ids)
        consensus_rows.append({
            "dimension": dim,
            "dimension_label": DIM_LABELS[dim],
            "n": len(human_ids),
            "consensus_3of3_n": counts[3],
            "consensus_3of3_pct": q(counts[3] / len(human_ids) * 100, 2),
            "consensus_2of3_n": counts[2],
            "consensus_2of3_pct": q(counts[2] / len(human_ids) * 100, 2),
            "no_majority_n": counts[1],
            "no_majority_pct": q(counts[1] / len(human_ids) * 100, 2),
        })
    write_csv(args.output_dir / "human_agreement.csv", agreement_rows)
    write_csv(args.output_dir / "human_consensus.csv", consensus_rows)

    portal_map = portal_aliases(humans[0]["portal"].astype(str)) if "portal" in humans[0].columns else {}
    if portal_map:
        dataset_rows = []
        for raw, alias in portal_map.items():
            n = int((humans[0]["portal"].astype(str) == raw).sum())
            dataset_rows.append({"portal": alias, "n": n})
        write_csv(args.output_dir / "dataset_portal_counts.csv", dataset_rows)

    coverage_rows = []
    for name, table in models:
        present = len(set(human_ids) & set(table.index))
        coverage_rows.append({
            "model": name,
            "n": present,
            "coverage_pct": q(present / len(human_ids) * 100, 1),
        })
    write_csv(args.output_dir / "model_coverage.csv", coverage_rows)

    common_ids = model_common_ids(human_ids, models)
    if len(common_ids) != 403:
        raise RuntimeError(f"Expected common set 403, got {len(common_ids)}")
    write_csv(
        args.output_dir / "common_set.csv",
        [{"article_id": aid} for aid in common_ids],
    )

    dimension_rows = []
    model_rows = []
    model_cache = {}
    for name, table in models:
        kappas = []
        exacts = []
        model_cache[name] = {}
        for dim in DIMS:
            ids = [aid for aid in common_ids if refs[dim][aid] is not None]
            y = [refs[dim][aid] for aid in ids]
            p = [norm_val(table.loc[aid, dim], dim) for aid in ids]
            kappa = safe_kappa(y, p, dim in ("tone", "balance"))
            exact = float(np.mean(np.asarray(y, dtype=object) == np.asarray(p, dtype=object)))
            mae = float(mean_absolute_error(y, p)) if dim in ("tone", "balance") else None
            kappas.append(kappa)
            exacts.append(exact)
            model_cache[name][dim] = (kappa, exact, mae)
            dimension_rows.append({
                "model": name,
                "dimension": dim,
                "dimension_label": DIM_LABELS[dim],
                "n": len(ids),
                "kappa": q(kappa),
                "exact_agreement_pct": q(exact * 100, 2),
                "mae": q(mae) if mae is not None else "",
            })
        model_rows.append({
            "model": name,
            "macro_kappa": q(np.nanmean(kappas)),
            "macro_exact_pct": q(np.mean(exacts) * 100, 2),
        })
    model_rows.sort(key=lambda row: float(row["macro_kappa"]), reverse=True)
    write_csv(args.output_dir / "llm_dimension_metrics.csv", dimension_rows)
    write_csv(args.output_dir / "llm_model_summary.csv", model_rows)

    top1 = model_rows[0]["model"]
    top2 = model_rows[1]["model"]
    model_lookup = dict(models)

    def macro_kappa(model_name, sampled_ids):
        table = model_lookup[model_name]
        values = []
        for dim in DIMS:
            ids = [aid for aid in sampled_ids if refs[dim][aid] is not None]
            y = [refs[dim][aid] for aid in ids]
            p = [norm_val(table.loc[aid, dim], dim) for aid in ids]
            values.append(safe_kappa(y, p, dim in ("tone", "balance")))
        return float(np.nanmean(values))

    diffs = []
    for _ in range(args.bootstrap):
        idx = rng.integers(0, len(common_ids), size=len(common_ids))
        sampled = [common_ids[i] for i in idx]
        diffs.append(macro_kappa(top1, sampled) - macro_kappa(top2, sampled))
    low, high = percentile_ci(diffs)
    write_csv(args.output_dir / "top2_macro_kappa_bootstrap.csv", [{
        "model_1": top1,
        "model_2": top2,
        "observed_difference": q(float(model_rows[0]["macro_kappa"]) - float(model_rows[1]["macro_kappa"])),
        "ci95_low": q(low),
        "ci95_high": q(high),
        "bootstrap_replicates": args.bootstrap,
        "seed": args.seed,
    }])

    difficulty_rows = []
    difficulty_summary = []
    model_macro = {}
    for name, table in models:
        vals3 = []
        vals2 = []
        for dim in DIMS:
            row = {"model": name, "dimension": dim}
            for level, target in ((3, vals3), (2, vals2)):
                ids = [
                    aid
                    for aid in common_ids
                    if refs[dim][aid] is not None and consensus[dim][aid] == level
                ]
                value = float(np.mean([
                    norm_val(table.loc[aid, dim], dim) == refs[dim][aid]
                    for aid in ids
                ]))
                target.append(value)
                row[f"exact_{level}of3_pct"] = q(value * 100, 2)
            row["drop_percentage_points"] = q((np.mean(vals3[-1:]) - np.mean(vals2[-1:])) * 100, 2)
            difficulty_rows.append(row)
        model_macro[name] = (float(np.mean(vals3)), float(np.mean(vals2)))
        difficulty_summary.append({
            "model": name,
            "macro_exact_3of3_pct": q(model_macro[name][0] * 100, 2),
            "macro_exact_2of3_pct": q(model_macro[name][1] * 100, 2),
            "drop_percentage_points": q((model_macro[name][0] - model_macro[name][1]) * 100, 2),
        })
    average3 = float(np.mean([v[0] for v in model_macro.values()]))
    average2 = float(np.mean([v[1] for v in model_macro.values()]))
    difficulty_summary.append({
        "model": "Prosjek 17 modela",
        "macro_exact_3of3_pct": q(average3 * 100, 2),
        "macro_exact_2of3_pct": q(average2 * 100, 2),
        "drop_percentage_points": q((average3 - average2) * 100, 2),
    })
    write_csv(args.output_dir / "human_consensus_difficulty.csv", difficulty_rows)
    write_csv(args.output_dir / "human_consensus_difficulty_summary.csv", difficulty_summary)

    human_tone = [refs["tone"][aid] for aid in common_ids]
    hct = Counter(human_tone)
    tone_rows = [{
        "source": "Ljudska referenca",
        **{f"tone_{value}": q(hct[value] / len(human_tone) * 100, 2) for value in TONE_ORDER},
        "mean_abs_tone": q(np.mean(np.abs(human_tone))),
        "extreme_pct": q((hct[-2] + hct[2]) / len(human_tone) * 100, 2),
    }]
    direction_rows = []
    for name, table in models:
        pred = [norm_val(table.loc[aid, "tone"], "tone") for aid in common_ids]
        counts = Counter(pred)
        tone_rows.append({
            "source": name,
            **{f"tone_{value}": q(counts[value] / len(pred) * 100, 2) for value in TONE_ORDER},
            "mean_abs_tone": q(np.mean(np.abs(pred))),
            "extreme_pct": q((counts[-2] + counts[2]) / len(pred) * 100, 2),
        })
        errors = [(h, p) for h, p in zip(human_tone, pred) if h != p]
        lower = sum(abs(p) < abs(h) for h, p in errors)
        higher = sum(abs(p) > abs(h) for h, p in errors)
        same = len(errors) - lower - higher
        direction_rows.append({
            "model": name,
            "errors_n": len(errors),
            "toward_lower_abs_pct": q(lower / len(errors) * 100, 2),
            "toward_higher_abs_pct": q(higher / len(errors) * 100, 2),
            "same_magnitude_pct": q(same / len(errors) * 100, 2),
        })
    model_tone_rows = tone_rows[1:]
    avg_tone = {"source": "Prosjek 17 modela"}
    for key in [f"tone_{value}" for value in TONE_ORDER] + ["mean_abs_tone", "extreme_pct"]:
        avg_tone[key] = q(np.mean([float(row[key]) for row in model_tone_rows]), 2)
    tone_rows.append(avg_tone)
    direction_rows.append({
        "model": "Prosjek 17 modela",
        "errors_n": q(np.mean([row["errors_n"] for row in direction_rows]), 2),
        "toward_lower_abs_pct": q(np.mean([float(row["toward_lower_abs_pct"]) for row in direction_rows]), 2),
        "toward_higher_abs_pct": q(np.mean([float(row["toward_higher_abs_pct"]) for row in direction_rows]), 2),
        "same_magnitude_pct": q(np.mean([float(row["same_magnitude_pct"]) for row in direction_rows]), 2),
    })
    write_csv(args.output_dir / "tone_distribution.csv", tone_rows)
    write_csv(args.output_dir / "tone_error_direction.csv", direction_rows)

    lean_ids = [aid for aid in common_ids if refs["political_lean"][aid] is not None]
    human_lean = [refs["political_lean"][aid] for aid in lean_ids]
    hc = Counter(human_lean)
    lean_rows = [{
        "source": "Ljudska referenca",
        "neutral_pct": q(hc["neutralno"] / len(human_lean) * 100, 2),
        "unclear_pct": q(hc["nejasno"] / len(human_lean) * 100, 2),
        "directed_pct": q((len(human_lean) - hc["neutralno"] - hc["nejasno"]) / len(human_lean) * 100, 2),
    }]
    transition_rows = []
    for name, table in models:
        pred = [norm_val(table.loc[aid, "political_lean"], "political_lean") for aid in lean_ids]
        counts = Counter(pred)
        lean_rows.append({
            "source": name,
            "neutral_pct": q(counts["neutralno"] / len(pred) * 100, 2),
            "unclear_pct": q(counts["nejasno"] / len(pred) * 100, 2),
            "directed_pct": q((len(pred) - counts["neutralno"] - counts["nejasno"]) / len(pred) * 100, 2),
        })
        directed = [i for i, value in enumerate(human_lean) if value not in ("neutralno", "nejasno")]
        neutral = [i for i, value in enumerate(human_lean) if value == "neutralno"]
        transition_rows.append({
            "model": name,
            "directed_to_neutral_pct": q(np.mean([pred[i] == "neutralno" for i in directed]) * 100, 2),
            "neutral_to_directed_pct": q(np.mean([pred[i] not in ("neutralno", "nejasno") for i in neutral]) * 100, 2),
        })
    lean_rows.append({
        "source": "Prosjek 17 modela",
        "neutral_pct": q(np.mean([float(row["neutral_pct"]) for row in lean_rows[1:]]), 2),
        "unclear_pct": q(np.mean([float(row["unclear_pct"]) for row in lean_rows[1:]]), 2),
        "directed_pct": q(np.mean([float(row["directed_pct"]) for row in lean_rows[1:]]), 2),
    })
    write_csv(args.output_dir / "lean_distribution.csv", lean_rows)
    write_csv(args.output_dir / "lean_transitions.csv", transition_rows)

    recall_rows = []
    for dim, cats in (("political_lean", LEAN_CATS), ("framing", FRAME_CATS)):
        ids = [aid for aid in common_ids if refs[dim][aid] is not None]
        for cat in cats:
            cat_ids = [aid for aid in ids if refs[dim][aid] == cat]
            if not cat_ids:
                continue
            recalls = []
            for _, table in models:
                recalls.append(np.mean([
                    norm_val(table.loc[aid, dim], dim) == cat
                    for aid in cat_ids
                ]))
            recall_rows.append({
                "dimension": dim,
                "category": cat,
                "human_reference_n": len(cat_ids),
                "avg_model_recall_pct": q(np.mean(recalls) * 100, 2),
            })
    write_csv(args.output_dir / "category_recall.csv", recall_rows)

    frame_ids = [aid for aid in common_ids if refs["framing"][aid] is not None]
    confusion = Counter()
    for _, table in models:
        for aid in frame_ids:
            human_value = refs["framing"][aid]
            model_value = norm_val(table.loc[aid, "framing"], "framing")
            if human_value != model_value:
                confusion[(human_value, model_value)] += 1
    total_confusions = sum(confusion.values())
    confusion_rows = [{
        "human": human,
        "model": model,
        "n": n,
        "pct_of_all_framing_errors": q(n / total_confusions * 100, 2),
    } for (human, model), n in confusion.most_common()]
    write_csv(args.output_dir / "framing_confusions.csv", confusion_rows)

    if portal_map:
        human_portal_rows = []
        model_portal_rows = []
        rankings = {}
        raw_portal = humans[0]["portal"].astype(str)
        for raw, alias in portal_map.items():
            ids = [aid for aid in human_ids if str(humans[0].loc[aid, "portal"]) == raw]
            tone = Counter(refs["tone"][aid] for aid in ids)
            balance = Counter(refs["balance"][aid] for aid in ids)
            frames = Counter(refs["framing"][aid] for aid in ids if refs["framing"][aid] is not None)
            leans = Counter(refs["political_lean"][aid] for aid in ids if refs["political_lean"][aid] is not None)
            human_portal_rows.append({
                "portal": alias,
                "n": len(ids),
                "tone_negative_pct": q((tone[-2] + tone[-1]) / len(ids) * 100, 2),
                "tone_neutral_pct": q(tone[0] / len(ids) * 100, 2),
                "tone_positive_pct": q((tone[1] + tone[2]) / len(ids) * 100, 2),
                "balance_0_pct": q(balance[0] / len(ids) * 100, 2),
                "balance_2_pct": q(balance[2] / len(ids) * 100, 2),
                "dominant_framing": frames.most_common(1)[0][0],
                "dominant_framing_pct": q(frames.most_common(1)[0][1] / sum(frames.values()) * 100, 2),
                "neutral_lean_pct": q(leans["neutralno"] / sum(leans.values()) * 100, 2),
            })
            common_portal = [aid for aid in common_ids if str(humans[0].loc[aid, "portal"]) == raw]
            rankings[alias] = []
            for name, table in models:
                kappas = []
                for dim in DIMS:
                    ids2 = [aid for aid in common_portal if refs[dim][aid] is not None]
                    y = [refs[dim][aid] for aid in ids2]
                    p = [norm_val(table.loc[aid, dim], dim) for aid in ids2]
                    kappas.append(safe_kappa(y, p, dim in ("tone", "balance")))
                macro = float(np.nanmean(kappas))
                rankings[alias].append((name, macro))
                model_portal_rows.append({
                    "portal": alias,
                    "model": name,
                    "n": len(common_portal),
                    "macro_kappa": q(macro),
                })
        write_csv(args.output_dir / "portal_human_distributions.csv", human_portal_rows)
        write_csv(args.output_dir / "portal_model_metrics.csv", model_portal_rows)
        correlation_rows = []
        aliases = sorted(rankings)
        model_names = [name for name, _ in models]
        for i in range(len(aliases)):
            for j in range(i + 1, len(aliases)):
                a, b = aliases[i], aliases[j]
                da, db = dict(rankings[a]), dict(rankings[b])
                rho = spearmanr([da[m] for m in model_names], [db[m] for m in model_names]).statistic
                correlation_rows.append({"portal_1": a, "portal_2": b, "spearman_rho": q(rho)})
        write_csv(args.output_dir / "portal_ranking_correlations.csv", correlation_rows)

if __name__ == "__main__":
    main()

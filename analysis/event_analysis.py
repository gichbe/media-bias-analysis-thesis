from __future__ import annotations

import argparse
from collections import Counter
from itertools import combinations
from pathlib import Path

import numpy as np
import pandas as pd

from common import (
    DIMS,
    DIM_LABELS,
    build_human_reference,
    load_humans,
    mode_value,
    portal_aliases,
    q,
    write_csv,
)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--human-dir", type=Path, default=Path("data/annotations/human"))
    parser.add_argument("--manifest", type=Path, default=Path("data/events/event_manifest.csv"))
    parser.add_argument("--output-dir", type=Path, default=Path("results/events"))
    args = parser.parse_args()

    args.output_dir.mkdir(parents=True, exist_ok=True)
    humans, human_ids = load_humans(args.human_dir)
    refs, _, _ = build_human_reference(humans, human_ids)
    manifest = pd.read_csv(args.manifest)
    required = {"event_id", "article_id", "portal"}
    missing = required - set(manifest.columns)
    if missing:
        raise RuntimeError(f"Event manifest missing columns {sorted(missing)}")
    manifest["article_id"] = manifest["article_id"].astype(str)
    if len(manifest) != 72 or manifest["event_id"].nunique() != 19:
        raise RuntimeError("Expected 72 articles across 19 events")
    if not set(manifest["article_id"]).issubset(set(human_ids)):
        raise RuntimeError("Event manifest contains unknown article_id values")
    aliases = portal_aliases(manifest["portal"].astype(str))
    manifest["portal_alias"] = manifest["portal"].astype(str).map(aliases)

    pair_rows = []
    event_rows = []
    for event_id, group in manifest.groupby("event_id", sort=True):
        ids = group["article_id"].tolist()
        for dim in DIMS:
            values = [refs[dim][aid] for aid in ids]
            valid = [value for value in values if value is not None]
            event_rows.append({
                "event_id": event_id,
                "dimension": dim,
                "dimension_label": DIM_LABELS[dim],
                "n_articles": len(ids),
                "n_valid": len(valid),
                "full_consensus": int(len(valid) == len(values) and len(set(valid)) == 1),
            })
            for a, b in combinations(ids, 2):
                va, vb = refs[dim][a], refs[dim][b]
                if va is None or vb is None:
                    continue
                pair_rows.append({
                    "event_id": event_id,
                    "dimension": dim,
                    "equal": int(va == vb),
                    "abs_difference": abs(int(va) - int(vb)) if dim in ("tone", "balance") else np.nan,
                })
    pair_df = pd.DataFrame(pair_rows)
    event_df = pd.DataFrame(event_rows)
    summary = []
    for dim in DIMS:
        p = pair_df[pair_df["dimension"] == dim]
        e = event_df[event_df["dimension"] == dim]
        summary.append({
            "dimension": dim,
            "dimension_label": DIM_LABELS[dim],
            "n_events": len(e),
            "n_valid_pairs": len(p),
            "pairwise_exact_pct": q(p["equal"].mean() * 100, 2),
            "mean_abs_difference": q(p["abs_difference"].mean(), 4) if dim in ("tone", "balance") else "",
            "full_event_consensus_n": int(e["full_consensus"].sum()),
            "full_event_consensus_pct": q(e["full_consensus"].mean() * 100, 2),
        })
    write_csv(args.output_dir / "same_event_agreement.csv", summary)

    same_actor_events = []
    for event_id, group in manifest.groupby("event_id", sort=True):
        ids = group["article_id"].tolist()
        actors = [refs["dominant_actor"][aid] for aid in ids]
        if all(value is not None for value in actors) and len(set(actors)) == 1:
            tones = [refs["tone"][aid] for aid in ids]
            same_actor_events.append({
                "event_id": event_id,
                "n_articles": len(ids),
                "tone_full_consensus": int(len(set(tones)) == 1),
                "tone_min": min(tones),
                "tone_max": max(tones),
            })
    write_csv(args.output_dir / "same_actor_events.csv", same_actor_events)
    write_csv(args.output_dir / "same_actor_event_summary.csv", [{
        "events_with_same_actor": len(same_actor_events),
        "tone_full_consensus_n": sum(row["tone_full_consensus"] for row in same_actor_events),
    }])

    five_portal_rows = []
    for event_id, group in manifest.groupby("event_id", sort=True):
        if group["portal_alias"].nunique() != 5:
            continue
        ids = group["article_id"].tolist()
        tones = [refs["tone"][aid] for aid in ids]
        balances = [refs["balance"][aid] for aid in ids]
        frames = [refs["framing"][aid] for aid in ids if refs["framing"][aid] is not None]
        leans = [refs["political_lean"][aid] for aid in ids if refs["political_lean"][aid] is not None]
        frame_counts = Counter(frames)
        lean_counts = Counter(leans)
        five_portal_rows.append({
            "event_id": event_id,
            "tone_min": min(tones),
            "tone_max": max(tones),
            "dominant_framing": frame_counts.most_common(1)[0][0],
            "dominant_framing_n": frame_counts.most_common(1)[0][1],
            "framing_valid_n": len(frames),
            "balance_min": min(balances),
            "balance_max": max(balances),
            "dominant_lean": lean_counts.most_common(1)[0][0] if leans else "",
            "dominant_lean_n": lean_counts.most_common(1)[0][1] if leans else 0,
            "lean_valid_n": len(leans),
        })
    write_csv(args.output_dir / "five_portal_events.csv", five_portal_rows)

    public_event_rows = []
    for _, row in manifest.sort_values(["event_id", "portal_alias"]).iterrows():
        aid = str(row["article_id"])
        public_event_rows.append({
            "event_id": row["event_id"],
            "article_id": aid,
            "portal": row["portal_alias"],
            **{dim: refs[dim][aid] for dim in DIMS},
        })
    write_csv(args.output_dir / "event_reference_labels.csv", public_event_rows)

if __name__ == "__main__":
    main()

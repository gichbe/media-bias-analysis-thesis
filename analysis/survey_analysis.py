from __future__ import annotations

import argparse
import re
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import wilcoxon

from common import holm_adjust, mode_value, q, write_csv

STIMULI = ("P1A", "P1B", "P2A", "P2B", "P3A", "P3B", "P4A", "P4B", "P5A", "P5B")
PAIRS = ("P1", "P2", "P3", "P4", "P5")

def first_int(value):
    match = re.search(r"[+-]?\d+", str(value))
    return int(match.group()) if match else np.nan

def find_column(columns, stimulus, phrase):
    matches = [column for column in columns if column.startswith(f"[{stimulus}]") and phrase in column]
    if len(matches) != 1:
        raise RuntimeError(f"Could not uniquely resolve {stimulus} {phrase}")
    return matches[0]

def normalize_frame(value):
    text = str(value).strip().lower()
    if text.startswith("neutral"):
        return "neutralni"
    return text

def normalize_source(value):
    text = str(value).strip().lower()
    if "oba" in text:
        return "oba"
    if "formulacije" in text or "medija" in text or "uredništva" in text:
        return "medij"
    if "citata" in text or "aktera" in text or "izvora" in text:
        return "citirani_akter"
    if "nema" in text:
        return "nema"
    return "nije_moguce_procijeniti"

def load_human(path):
    table = pd.read_csv(path)
    rows = []
    for respondent, (_, row) in enumerate(table.iterrows(), 1):
        for stimulus in STIMULI:
            tone_col = find_column(table.columns, stimulus, "evaluativni ton")
            frame_col = find_column(table.columns, stimulus, "Koji okvir")
            bias_col = find_column(table.columns, stimulus, "pristrasno ili jednostrano")
            source_col = find_column(table.columns, stimulus, "Odakle prvenstveno")
            rows.append({
                "respondent_id": f"R{respondent:03d}",
                "stimulus_id": stimulus,
                "pair_id": stimulus[:2],
                "version": stimulus[-1],
                "tone": first_int(row[tone_col]),
                "framing": normalize_frame(row[frame_col]),
                "bias": first_int(row[bias_col]),
                "evaluative_source": normalize_source(row[source_col]),
            })
    return pd.DataFrame(rows)

def paired_wilcoxon(a, b):
    diff = np.asarray(a, dtype=float) - np.asarray(b, dtype=float)
    if np.all(diff == 0):
        return 1.0
    return float(wilcoxon(diff, zero_method="wilcox", correction=False, alternative="two-sided", method="auto").pvalue)

def sign_direction(a, b):
    if a > b:
        return 1
    if a < b:
        return -1
    return 0

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--human", type=Path, default=Path("data/survey/human_responses.csv"))
    parser.add_argument("--llm", type=Path, default=Path("data/survey/llm_results.csv"))
    parser.add_argument("--output-dir", type=Path, default=Path("results/survey"))
    args = parser.parse_args()

    args.output_dir.mkdir(parents=True, exist_ok=True)
    human = load_human(args.human)
    if human["respondent_id"].nunique() != 70:
        raise RuntimeError(f"Expected 70 respondents, got {human['respondent_id'].nunique()}")
    write_csv(args.output_dir / "human_responses_long.csv", human)

    pair_rows = []
    tone_p = []
    bias_p = []
    for pair in PAIRS:
        a = human[(human["pair_id"] == pair) & (human["version"] == "A")].sort_values("respondent_id")
        b = human[(human["pair_id"] == pair) & (human["version"] == "B")].sort_values("respondent_id")
        if list(a["respondent_id"]) != list(b["respondent_id"]):
            raise RuntimeError(f"Unpaired responses for {pair}")
        tp = paired_wilcoxon(a["tone"], b["tone"])
        bp = paired_wilcoxon(a["bias"], b["bias"])
        tone_p.append(tp)
        bias_p.append(bp)
        frame_a = mode_value(a["framing"])
        frame_b = mode_value(b["framing"])
        source_a = mode_value(a["evaluative_source"])
        source_b = mode_value(b["evaluative_source"])
        tone_diff = a["tone"].to_numpy() - b["tone"].to_numpy()
        bias_diff = a["bias"].to_numpy() - b["bias"].to_numpy()
        pair_rows.append({
            "pair_id": pair,
            "tone_median_a": q(a["tone"].median(), 2),
            "tone_median_b": q(b["tone"].median(), 2),
            "tone_direction_a_minus_b": sign_direction(a["tone"].median(), b["tone"].median()),
            "tone_a_lower_n": int(np.sum(tone_diff < 0)),
            "tone_equal_n": int(np.sum(tone_diff == 0)),
            "tone_a_higher_n": int(np.sum(tone_diff > 0)),
            "tone_p_raw": tp,
            "bias_median_a": q(a["bias"].median(), 2),
            "bias_median_b": q(b["bias"].median(), 2),
            "bias_direction_a_minus_b": sign_direction(a["bias"].median(), b["bias"].median()),
            "bias_a_lower_n": int(np.sum(bias_diff < 0)),
            "bias_equal_n": int(np.sum(bias_diff == 0)),
            "bias_a_higher_n": int(np.sum(bias_diff > 0)),
            "bias_p_raw": bp,
            "dominant_framing_a": frame_a,
            "dominant_framing_b": frame_b,
            "framing_changed_pct": q(np.mean(a["framing"].to_numpy() != b["framing"].to_numpy()) * 100, 2),
            "dominant_source_a": source_a,
            "dominant_source_b": source_b,
            "source_changed_pct": q(np.mean(a["evaluative_source"].to_numpy() != b["evaluative_source"].to_numpy()) * 100, 2),
        })
    tone_adj = holm_adjust(tone_p)
    bias_adj = holm_adjust(bias_p)
    for row, tp, bp in zip(pair_rows, tone_adj, bias_adj):
        row["tone_p_holm"] = tp
        row["tone_significant"] = bool(tp < 0.05)
        row["bias_p_holm"] = bp
        row["bias_significant"] = bool(bp < 0.05)
    write_csv(args.output_dir / "human_pair_summary.csv", pair_rows)
    write_csv(args.output_dir / "human_significance_summary.csv", [{
        "tone_significant_pairs": sum(row["tone_significant"] for row in pair_rows),
        "bias_significant_pairs": sum(row["bias_significant"] for row in pair_rows),
    }])

    if not args.llm.exists():
        return
    llm = pd.read_csv(args.llm)
    required = {"stimulus_id", "run", "tone", "framing", "bias", "evaluative_source", "status"}
    missing = required - set(llm.columns)
    if missing:
        raise RuntimeError(f"LLM survey file missing columns {sorted(missing)}")
    llm = llm[llm["status"].astype(str).str.lower().eq("ok")].copy()
    if "model" in llm.columns:
        model_col = "model"
    elif "model_requested" in llm.columns:
        model_col = "model_requested"
    elif "model_actual" in llm.columns:
        model_col = "model_actual"
    else:
        raise RuntimeError("LLM survey file needs a model column")
    llm["framing"] = llm["framing"].map(normalize_frame)
    llm["evaluative_source"] = llm["evaluative_source"].map(normalize_source)

    human_direction = {
        row["pair_id"]: {
            "tone": row["tone_direction_a_minus_b"],
            "bias": row["bias_direction_a_minus_b"],
        }
        for row in pair_rows
    }
    llm_rows = []
    for model, group in llm.groupby(model_col, sort=True):
        stimulus_agg = {}
        stable_tone = 0
        stable_bias = 0
        stable_frame = 0
        stable_source = 0
        for stimulus in STIMULI:
            g = group[group["stimulus_id"] == stimulus]
            if len(g) == 0:
                continue
            stimulus_agg[stimulus] = {
                "tone": float(np.median(g["tone"].astype(float))),
                "bias": float(np.median(g["bias"].astype(float))),
                "framing": mode_value(g["framing"]),
                "evaluative_source": mode_value(g["evaluative_source"]),
            }
            stable_tone += int(g["tone"].nunique() == 1)
            stable_bias += int(g["bias"].nunique() == 1)
            stable_frame += int(g["framing"].nunique() == 1)
            stable_source += int(g["evaluative_source"].nunique() == 1)
        tone_direction_matches = 0
        bias_direction_matches = 0
        comparable = 0
        for pair in PAIRS:
            a = f"{pair}A"
            b = f"{pair}B"
            if a not in stimulus_agg or b not in stimulus_agg:
                continue
            comparable += 1
            tone_direction_matches += int(
                sign_direction(stimulus_agg[a]["tone"], stimulus_agg[b]["tone"])
                == human_direction[pair]["tone"]
            )
            bias_direction_matches += int(
                sign_direction(stimulus_agg[a]["bias"], stimulus_agg[b]["bias"])
                == human_direction[pair]["bias"]
            )
        llm_rows.append({
            "model": model,
            "tone_direction_matches": tone_direction_matches,
            "bias_direction_matches": bias_direction_matches,
            "comparable_pairs": comparable,
            "stable_tone_stimuli": stable_tone,
            "stable_bias_stimuli": stable_bias,
            "stable_framing_stimuli": stable_frame,
            "stable_source_stimuli": stable_source,
            "total_stimuli": len(stimulus_agg),
        })
    write_csv(args.output_dir / "llm_summary.csv", llm_rows)

if __name__ == "__main__":
    main()

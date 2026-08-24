from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

DIM_ORDER = ("dominant_actor", "tone", "framing", "balance", "political_lean")
DIM_LABELS = {
    "dominant_actor": "Dominantni akter",
    "tone": "Ton",
    "framing": "Uokviravanje",
    "balance": "Balansiranost",
    "political_lean": "Politička usmjerenost",
}

def save(fig, directory, name):
    directory.mkdir(parents=True, exist_ok=True)
    fig.savefig(directory / f"{name}.png", dpi=300, bbox_inches="tight")
    fig.savefig(directory / f"{name}.pdf", bbox_inches="tight")
    plt.close(fig)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--results-dir", type=Path, default=Path("results"))
    parser.add_argument("--output-dir", type=Path, default=Path("figures"))
    args = parser.parse_args()
    main_dir = args.results_dir / "main"

    table = pd.read_csv(main_dir / "human_agreement.csv")
    table["dimension"] = pd.Categorical(table["dimension"], DIM_ORDER, ordered=True)
    table = table.sort_values("dimension")
    values = table["krippendorff_alpha"].to_numpy()
    low = table["alpha_ci95_low"].to_numpy()
    high = table["alpha_ci95_high"].to_numpy()
    y = np.arange(len(table))
    fig, ax = plt.subplots(figsize=(8.5, 5.2))
    ax.errorbar(values, y, xerr=np.vstack([values-low, high-values]), fmt="o", capsize=5)
    ax.set_yticks(y)
    ax.set_yticklabels([DIM_LABELS[x] for x in table["dimension"]])
    ax.set_xlim(0, 1)
    ax.set_xlabel("Krippendorffov α")
    ax.invert_yaxis()
    save(fig, args.output_dir, "4_1_human_agreement")

    table = pd.read_csv(main_dir / "llm_model_summary.csv").sort_values("macro_kappa")
    fig, ax = plt.subplots(figsize=(9, 8))
    bars = ax.barh(table["model"], table["macro_kappa"])
    ax.set_xlabel("Makroprosjek κ")
    ax.set_xlim(0, 0.8)
    ax.bar_label(bars, labels=[f"{x:.3f}" for x in table["macro_kappa"]], padding=3, fontsize=8)
    save(fig, args.output_dir, "4_2_macro_kappa")

    metrics = pd.read_csv(main_dir / "llm_dimension_metrics.csv")
    order = pd.read_csv(main_dir / "llm_model_summary.csv").sort_values("macro_kappa", ascending=False)["model"].tolist()
    pivot = metrics.pivot(index="model", columns="dimension", values="kappa").reindex(index=order, columns=DIM_ORDER)
    data = pivot.to_numpy(dtype=float)
    fig, ax = plt.subplots(figsize=(10, 10.5))
    image = ax.imshow(data, aspect="auto", vmin=0, vmax=1, cmap="Blues")
    ax.set_xticks(np.arange(len(DIM_ORDER)))
    ax.set_xticklabels([DIM_LABELS[x] for x in DIM_ORDER], rotation=25, ha="right")
    ax.set_yticks(np.arange(len(order)))
    ax.set_yticklabels(order)
    for i in range(data.shape[0]):
        for j in range(data.shape[1]):
            value = data[i, j]
            ax.text(j, i, "—" if np.isnan(value) else f"{value:.2f}", ha="center", va="center", fontsize=8, color="white" if value >= 0.55 else "black")
    fig.colorbar(image, ax=ax).set_label("κ")
    save(fig, args.output_dir, "4_3_dimension_kappa")

    table = pd.read_csv(main_dir / "human_consensus_difficulty_summary.csv").sort_values("macro_exact_3of3_pct")
    y = np.arange(len(table))
    width = 0.36
    fig, ax = plt.subplots(figsize=(10, 8.5))
    ax.barh(y + width/2, table["macro_exact_3of3_pct"], height=width, label="Ljudski konsenzus 3/3")
    ax.barh(y - width/2, table["macro_exact_2of3_pct"], height=width, label="Ljudski konsenzus 2/3")
    ax.set_yticks(y)
    ax.set_yticklabels(table["model"])
    ax.set_xlim(0, 100)
    ax.set_xlabel("Tačno slaganje s referencom (%)")
    ax.legend()
    save(fig, args.output_dir, "4_4_consensus_difficulty")

    table = pd.read_csv(main_dir / "tone_distribution.csv")
    human = table[table["source"] == "Ljudska referenca"].iloc[0]
    avg = table[table["source"] == "Prosjek 17 modela"].iloc[0]
    cols = ["tone_-2", "tone_-1", "tone_0", "tone_1", "tone_2"]
    labels = ["−2", "−1", "0", "+1", "+2"]
    x = np.arange(5)
    width = 0.36
    fig, ax = plt.subplots(figsize=(8.5, 5.5))
    ax.bar(x-width/2, human[cols].astype(float), width, label="Ljudska referenca")
    ax.bar(x+width/2, avg[cols].astype(float), width, label="Prosjek 17 modela")
    ax.set_xticks(x)
    ax.set_xticklabels(labels)
    ax.set_ylabel("Udio oznaka (%)")
    ax.set_xlabel("Ton")
    ax.legend()
    save(fig, args.output_dir, "4_5_tone_distribution")

    table = pd.read_csv(main_dir / "lean_distribution.csv")
    human = table[table["source"] == "Ljudska referenca"].iloc[0]
    avg = table[table["source"] == "Prosjek 17 modela"].iloc[0]
    cols = ["neutral_pct", "unclear_pct", "directed_pct"]
    labels = ["Neutralna", "Nejasna", "Usmjerena"]
    x = np.arange(3)
    fig, ax = plt.subplots(figsize=(8.5, 5.5))
    ax.bar(x-width/2, human[cols].astype(float), width, label="Ljudska referenca")
    ax.bar(x+width/2, avg[cols].astype(float), width, label="Prosjek 17 modela")
    ax.set_xticks(x)
    ax.set_xticklabels(labels)
    ax.set_ylabel("Udio oznaka (%)")
    ax.legend()
    save(fig, args.output_dir, "4_6_lean_distribution")

    event_path = args.results_dir / "events" / "same_event_agreement.csv"
    if event_path.exists():
        table = pd.read_csv(event_path)
        table["dimension"] = pd.Categorical(table["dimension"], DIM_ORDER, ordered=True)
        table = table.sort_values("dimension")
        fig, ax = plt.subplots(figsize=(8.5, 5.5))
        ax.bar([DIM_LABELS[x] for x in table["dimension"]], table["full_event_consensus_pct"])
        ax.set_ylabel("Događaji s potpunim slaganjem (%)")
        ax.tick_params(axis="x", rotation=25)
        save(fig, args.output_dir, "4_7_same_event_agreement")

    survey_path = args.results_dir / "survey" / "human_pair_summary.csv"
    if survey_path.exists():
        table = pd.read_csv(survey_path).sort_values("pair_id")
        x = np.arange(len(table))
        fig, axes = plt.subplots(1, 2, figsize=(12, 5.5))
        axes[0].bar(x-width/2, table["tone_median_a"], width, label="Verzija A")
        axes[0].bar(x+width/2, table["tone_median_b"], width, label="Verzija B")
        axes[0].set_xticks(x)
        axes[0].set_xticklabels(table["pair_id"])
        axes[0].set_ylim(-2.2, 2.2)
        axes[0].set_ylabel("Medijan procjene tona")
        axes[0].legend()
        axes[1].bar(x-width/2, table["bias_median_a"], width, label="Verzija A")
        axes[1].bar(x+width/2, table["bias_median_b"], width, label="Verzija B")
        axes[1].set_xticks(x)
        axes[1].set_xticklabels(table["pair_id"])
        axes[1].set_ylim(0, 5.2)
        axes[1].set_ylabel("Medijan procjene pristrasnosti")
        axes[1].legend()
        save(fig, args.output_dir, "4_8_survey_ab")

    selection_path = args.results_dir / "article_selection" / "score_distribution.csv"
    if selection_path.exists():
        table = pd.read_csv(selection_path).sort_values("score")
        x = np.arange(len(table))
        fig, ax = plt.subplots(figsize=(8.5, 5.5))
        ax.bar(x-width/2, table["all_n"], width, label="Svi validno ocijenjeni naslovi")
        ax.bar(x+width/2, table["manual_reference_n"], width, label="Prethodno ručno odabrani")
        ax.set_xticks(x)
        ax.set_xticklabels(table["score"])
        ax.set_xlabel("Ocjena pogodnosti")
        ax.set_ylabel("Broj naslova")
        ax.legend()
        save(fig, args.output_dir, "4_9_article_selection")

if __name__ == "__main__":
    main()

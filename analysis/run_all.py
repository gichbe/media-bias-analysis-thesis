from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

def run(script, arguments):
    subprocess.run([sys.executable, str(script), *arguments], check=True)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--human-dir", default="data/annotations/human")
    parser.add_argument("--model-dir", default="data/annotations/models")
    parser.add_argument("--model-manifest", default="analysis/models.csv")
    parser.add_argument("--event-manifest", default="data/events/event_manifest.csv")
    parser.add_argument("--survey-human", default="data/survey/human_responses.csv")
    parser.add_argument("--survey-llm", default="data/survey/llm_results.csv")
    parser.add_argument("--selection", default="data/article_selection/selection_scores.csv")
    parser.add_argument("--bootstrap", default="2000")
    parser.add_argument("--seed", default="20260814")
    args = parser.parse_args()

    base = Path(__file__).resolve().parent
    shared = [
        "--human-dir", args.human_dir,
        "--model-dir", args.model_dir,
        "--model-manifest", args.model_manifest,
    ]
    run(base / "main_analysis.py", shared + ["--bootstrap", args.bootstrap, "--seed", args.seed])
    run(base / "targeted_actor_analysis.py", shared)
    run(base / "additional_statistics.py", shared + ["--bootstrap", args.bootstrap, "--seed", args.seed])
    if Path(args.event_manifest).exists():
        run(base / "event_analysis.py", ["--human-dir", args.human_dir, "--manifest", args.event_manifest])
    if Path(args.survey_human).exists():
        arguments = ["--human", args.survey_human]
        if Path(args.survey_llm).exists():
            arguments += ["--llm", args.survey_llm]
        run(base / "survey_analysis.py", arguments)
    if Path(args.selection).exists():
        run(base / "article_selection_analysis.py", ["--selection", args.selection])
    run(base / "make_figures.py", [])

if __name__ == "__main__":
    main()

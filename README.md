# Media Bias Analysis with Large Language Models

This repository contains the code, pseudonymized annotations, and supporting
materials for a bachelor's thesis on automated political media-bias analysis
with large language models (LLMs) in Bosnia and Herzegovina (BiH).

The study compares three independent human annotators with 17 LLMs on 458
Bosnian-language online news articles. Each article is annotated along five
dimensions:

1. dominant political actor;
2. tone toward that actor;
3. reporting frame;
4. balance of political perspectives; and
5. political lean.

The repository supports reproduction of the published statistical analyses
from pseudonymized labels. It does not distribute the underlying news corpus.

## Methodology at a glance

The human reference is constructed separately for each dimension. For tone and
balance, the reference is the median of the three ratings. For nominal
dimensions, the majority label is used; a reference is absent when all three
annotators chose different labels. The analysis measures human agreement with
Krippendorff's alpha and pairwise kappa/exact agreement, then compares each LLM
with the human reference using dimension-level and macro-averaged metrics.

The main cross-model comparison uses the 403 articles present in every model
output. Additional scripts examine:

- performance by human-consensus level;
- tone agreement when humans and models identify the same dominant actor;
- differences in coverage of the same event by several portals;
- a paired human survey and corresponding repeated LLM assessments; and
- enrichment in the automated article-selection procedure.

Bootstrap confidence intervals use a fixed default seed (`20260814`). See the
[annotation codebook](docs/codebook.md) for the complete coding rules and the
Bosnian category terms retained in the data.

## Repository structure

```text
analysis/          Statistical analyses and figure generation
data/annotations/  Pseudonymized human and LLM annotations
data/events/       Article-to-event mapping for cross-portal analysis
data/survey/       Original human-survey responses and LLM survey results
data/article_selection/
                   Original article-selection scores
docs/              English annotation codebook
src/               Multi-provider LLM annotation evaluator
config.example.json
                   Example corpus-specific actor configuration
```

Generated `results/` and `figures/` directories are ignored by Git.

## Public data and research-material preservation

The annotation files contain the labels needed to recompute the main
statistics. To protect the source corpus and research participants, they omit
article text, headlines, URLs, real outlet names, annotator identities, model
rationales, API identifiers, and other content metadata. Article IDs, outlet
names, and dominant actors are consistently pseudonymized across human and
model files, preserving the relationships required for agreement analysis.
See [data/annotations/README.md](data/annotations/README.md) for details.

The files under `data/` are original research materials and should not be
translated or normalized. Their Bosnian column headings, responses, and
categorical values are intentional. Likewise, the Bosnian prompt templates in
`src/llm_evaluator.py` are preserved exactly as used in the experiments.

## Setup

Python 3.11 or later is recommended.

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt
```

## Reproducing the analyses

Run all analyses and generate all figures from the repository root:

```bash
python3 analysis/run_all.py
```

By default, this writes CSV tables to `results/` and PNG/PDF figures to
`figures/`. The full run uses 2,000 bootstrap replicates. For a faster smoke
test, reduce that number without changing the input data:

```bash
python3 analysis/run_all.py --bootstrap 20
```

Individual analyses can also be run separately:

```bash
python3 analysis/main_analysis.py
python3 analysis/targeted_actor_analysis.py
python3 analysis/additional_statistics.py
python3 analysis/event_analysis.py
python3 analysis/survey_analysis.py
python3 analysis/article_selection_analysis.py
python3 analysis/make_figures.py
```

Use `python3 <script> --help` to inspect input, output, bootstrap, and seed
options. Scripts expect to be launched from the repository root unless all
relevant paths are supplied explicitly.

## LLM evaluator

`src/llm_evaluator.py` implements the multi-provider annotation pipeline used
to evaluate articles. It supports the provider/model identifiers configured by
the script, validates structured JSON responses, can resume interrupted CSV
output, and provides dry-run and prompt-preview modes. The private input corpus
and the corpus-specific political map are not included. `config.example.json`
documents the required configuration shape without disclosing those values.

The evaluator is included for methodological transparency, but the public
repository is not sufficient to rerun article annotation without the private
corpus, the original configuration, and provider credentials. Inspect its CLI
without making an API call with:

```bash
python3 src/llm_evaluator.py --help
```

Do not run provider-backed evaluation commands unless you intend to incur API
costs. The analysis scripts above operate entirely on the included results.

## Data conventions

Dataset column names, category labels, model identifiers, configuration keys,
and paths are stable interfaces and remain in their original form. In
particular, Bosnian labels such as `odgovornost` (responsibility frame),
`neutralan` (neutral), and `pro_vlast` (favoring the governing parties) are
explained in English in the codebook rather than renamed in the CSV files.

Because article identifiers were pseudonymized, the unit order can differ from
the internal working dataset. Recomputed bootstrap confidence intervals may
therefore differ minimally, while deterministic point estimates remain
unchanged.

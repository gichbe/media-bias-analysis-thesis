# Public annotation data

This directory contains the pseudonymized annotation outputs used in the
statistical analysis.

The published files do not contain article text, headlines, URLs, real outlet
names, annotator identities, model rationales, API identifiers, or other
content metadata.

`article_id` values were randomly remapped to `ART0001` and subsequent IDs.
Sources were remapped to `Portal A` through `Portal E`, and `dominant_actor`
values to `actor_001` and subsequent pseudonyms. The same mapping is used in
all human and model files, preserving the agreement structure needed for the
statistical analysis.

The annotation dimensions `tone`, `framing`, `balance`, and `political_lean`
remain in their original coding because they are required to reproduce the
results. See [`docs/codebook.md`](../../docs/codebook.md) for English
definitions and explanations of the retained Bosnian category labels.

## Layout

- `human/A1.csv`, `A2.csv`, and `A3.csv` contain the three independent human
  annotations.
- `models/*.csv` contain the LLM annotations. The filename-to-model mapping is
  recorded in [`analysis/models.csv`](../../analysis/models.csv).

These CSV files are original research materials. Do not translate or rename
their columns, category values, identifiers, or pseudonyms.

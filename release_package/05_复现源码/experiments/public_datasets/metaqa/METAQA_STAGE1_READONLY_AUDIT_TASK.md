# MetaQA Stage 1 Read-Only Audit Task

## Goal

This stage performs a read-only audit of the uploaded MetaQA raw dataset,
prepares a robust conversion script, and generates only a very small smoke
sample.

## Prohibited actions

- Do not run formal MetaQA evaluation.
- Do not run 300, 1300, 1800, or any other large-scale evaluation.
- Do not call any LLM or external API.
- Do not import data into Neo4j.
- Do not build a full vector index.
- Do not delete or modify raw data.
- Do not modify directories used by currently running formal experiments.

## Raw data

`experiments/public_datasets/metaqa/raw/dataset/MetaQA_clean`

## Outputs

- Audit script: `experiments/public_datasets/metaqa/scripts/audit_metaqa_raw.py`
- Conversion script: `experiments/public_datasets/metaqa/scripts/convert_metaqa_to_public_format.py`
- Audit report: `experiments/public_datasets/metaqa/reports/metaqa_raw_audit_report.md`
- Smoke outputs: `experiments/public_datasets/metaqa/processed/smoke`

## Acceptance criteria

- All 19 required raw files are checked.
- File line counts are reported.
- Every qtype file is checked against its aligned vanilla QA file.
- `kb.txt` parsing statistics and relation frequencies are reported.
- QA formats and aligned qtype samples are reported.
- At most five QA records per hop and split are converted in the smoke run.
- Graph smoke output is bounded to five edges when `--limit-per-split 5` is used.
- No formal evaluation, API, Neo4j import, vector indexing, or raw-data mutation occurs.


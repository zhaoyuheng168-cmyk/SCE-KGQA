# MetaQA Formal Experiment Protocol

## Research Questions

1. Can the same unified Core execute MetaQA typed routes without movie-domain
   logic inside the executor?
2. Does the start-entity revisit constraint improve cyclic multi-hop routes?
3. Does domain-configurable entity linking improve benchmark performance without
   harming other route families?
4. Are remaining errors attributable to framework behavior or raw-data
   ambiguity?

## Fixed Evaluation Setup

- Dataset: original MetaQA clean knowledge base and vanilla QA files.
- Split: test for final reporting; dev for preflight.
- Metrics: exact-match accuracy, macro precision, macro recall, and macro F1.
- Breakdowns: overall, hop, qtype, and failure category.
- Gold answers are never used to filter predictions.
- Same-string collision cases remain in the reported score.

## Ablation Matrix

| Variant | Entity linking | Start revisit constraint | Purpose |
|---|---|---|---|
| `full` | exact typed | enabled | Proposed unified Core |
| `no_revisit_constraint` | exact typed | disabled | Measure path-constraint contribution |
| `fuzzy_linking` | fuzzy typed | enabled | Measure entity-linking policy contribution |
| `no_both` | fuzzy typed | disabled | Weak unified-Core configuration |

## Execution Stages

1. Run a qtype-balanced dev preflight with `--max-per-qtype 10`.
2. Inspect outputs and runtime before any full run.
3. Run the four variants on the test split in separate output directories.
4. Compare overall, hop, qtype, and failure-category results.
5. Audit remaining failures without modifying raw data or gold answers.

## Safety Properties

- The runner defaults to dry-run mode.
- Execution requires the explicit confirmation token `RUN_FORMAL_METAQA`.
- Output directories must not already exist.
- The runner does not call APIs, Neo4j, vector indexes, or language models.
- The runner only reads raw MetaQA files.

## Current Bounded Evidence

The 141-question coverage smoke improved from **101/141** to **139/141** after
promoting configurable entity linking into the shared Core. The two remaining
errors are same-string collisions supported by valid graph evidence.

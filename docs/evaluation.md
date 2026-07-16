# Evaluation

## Formal protocol

The reported methods were evaluated on the same frozen set of 1300 questions.
The main comparison reports strict accuracy, strict Macro-F1, task-aware
success and task-aware Macro-F1. This repository does not rerun or rescore the
formal experiment.

The complete copied comparison table is
[`results/official/main_comparison_formal1300.csv`](../results/official/main_comparison_formal1300.csv).
The SCE-KGQA row reports:

| Metric | Frozen result |
|---|---:|
| Strict accuracy | 88.23% |
| Strict Macro-F1 | 79.05% |
| Task-aware success | 92.23% |
| Task-aware Macro-F1 | 85.15% |

Official LightRAG has no task-aware values in the copied source table; the
empty fields are retained rather than estimated.

## Ablation source

[`results/official/ablation_correctness_summary_public.csv`](../results/official/ablation_correctness_summary_public.csv)
is a public view of the frozen ablation output. Only the two internal
provenance-path columns were removed; metric names, rows and values were not
recalculated or changed.

The main comparison reports a formal Strict Accuracy of **88.23%**. The Full
System row in the ablation output is `0.8830769230769231`, which is reported as
**88.31%** after percentage conversion and two-decimal rounding. These values
come from two independent frozen outputs and differ by **1 of 1300 questions**.
Each value is used only inside its own experiment group: the main-comparison
result is compared with the baselines in the main table, while ablation
variants are compared with the Full System row in the ablation table. The two
Full System values must not be mixed or compared across tables.

This statement matches the submitted manuscript, whose ablation-table note
also records 88.23%, 88.31%, two frozen outputs and a 1/1300-question
difference.

## Interpretation boundary

The results support the effectiveness of the complete implementation under
the frozen regional science and technology finance setting. They do not by
themselves establish production readiness, universal-domain performance or
statistical superiority over every possible baseline.

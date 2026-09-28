# MetaQA Formal Five-Fold Template-Holdout Summary

## Scope

- Source data: MetaQA train split.
- Evaluation: five-fold, per-qtype template holdout.
- Unique normalized templates: **521**.
- Template overlap within every fold: **0**.
- Template overlap between test folds: **0**.
- Union of test folds: all **521** templates.
- Questions evaluated across five folds: **329,282**.
- Training unit: one representative per normalized training template.
- Evaluation unit: every question belonging to each held-out template.

## Fold Results

| Fold | Questions | Route Accuracy | End-to-End Exact Match | Macro F1 |
|---:|---:|---:|---:|---:|
| 0 | 68,195 | 82.512% | 82.024% | 84.002% |
| 1 | 67,855 | 75.791% | 74.307% | 76.962% |
| 2 | 66,029 | 70.764% | 70.948% | 72.905% |
| 3 | 64,718 | 82.537% | 82.146% | 83.662% |
| 4 | 62,485 | 87.221% | 86.477% | 88.055% |

## Mean and Standard Deviation Across Folds

| Metric | Mean | Standard deviation |
|---|---:|---:|
| Route Accuracy | **79.765%** | **6.473%** |
| End-to-End Exact Match | **79.180%** | **6.357%** |
| Macro F1 | **81.117%** | **6.075%** |

## Question-Weighted Results

| Metric | Weighted result |
|---|---:|
| Route Accuracy | **79.670%** |
| End-to-End Exact Match | **79.081%** |
| Macro F1 | **81.028%** |

## Question-Weighted Results by Hop

| Hop | Questions | Route Accuracy | End-to-End Exact Match | Macro F1 |
|---:|---:|---:|---:|---:|
| 1-hop | 96,106 | 85.359% | 82.133% | 85.498% |
| 2-hop | 118,980 | 85.334% | 85.793% | 85.976% |
| 3-hop | 114,196 | 68.981% | 69.520% | 72.111% |

## Runtime

- Total runtime for all five folds: **36.778 seconds**.
- Each unique normalized training template contributes one classifier example.
- Every question remains in evaluation exactly once across the five folds.

## Interpretation

The five-fold results confirm that performance on unseen question templates is
substantially below the Oracle-qtype execution result and varies with the
linguistic templates selected for evaluation.

The unified Core remains fast once a route is selected. The dominant end-to-end
bottleneck is route prediction for unseen language, especially for 3-hop
questions.

These results should be reported as supervised, in-domain template
generalization. They do not claim zero-shot natural-language transfer from the
Gansu domain to MetaQA.

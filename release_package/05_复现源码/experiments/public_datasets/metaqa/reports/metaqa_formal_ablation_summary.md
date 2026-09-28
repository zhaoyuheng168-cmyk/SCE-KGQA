# MetaQA Formal Unified-Core Ablation Summary

## Scope

- Dataset split: MetaQA test.
- Questions: **39,093**.
- Setting: **Oracle-qtype typed-path execution**, not end-to-end route prediction.
- The four configurations use the same knowledge base, questions, routes, and
  evaluation metrics.

## Ablation Matrix

| Configuration | Entity linking | Start-revisit constraint | Exact | Accuracy | Macro F1 | Runtime |
|---|---|---|---:|---:|---:|---:|
| Full unified Core | Exact typed | Enabled | 38,553 | 98.619% | 99.511% | 3.962 s |
| No revisit constraint | Exact typed | Disabled | 31,878 | 81.544% | 97.360% | 3.993 s |
| Fuzzy linking | Fuzzy typed | Enabled | 24,050 | 61.520% | 82.303% | 188.160 s |
| No both | Fuzzy typed | Disabled | 21,031 | 53.797% | 80.570% | 237.247 s |

## Accuracy by Hop

| Configuration | 1-hop | 2-hop | 3-hop |
|---|---:|---:|---:|
| Full unified Core | 94.571% | 100.000% | 100.000% |
| No revisit constraint | 94.571% | 100.000% | 53.237% |
| Fuzzy linking | 49.482% | 86.182% | 44.213% |
| No both | 49.482% | 86.182% | 23.063% |

## Paired Effects

Compared with Full:

- No revisit constraint loses **6,675** previously correct questions and gains
  none.
- Fuzzy linking loses **14,503** previously correct questions and gains none.
- No both loses **17,522** previously correct questions and gains none.

Compared with Fuzzy linking:

- Disabling the revisit constraint additionally loses **3,047** questions.
- It makes **28** previously incorrect fuzzy-linking questions exact through
  accidental error-set cancellation.
- The net loss is **3,019** exact matches.

Compared with No revisit constraint:

- Replacing exact linking with fuzzy linking additionally loses **10,847**
  questions and gains none.

## Joint-Ablation Failure Profile

| Failure type | Count |
|---|---:|
| `over_return` | 17,962 |
| `mixed_answer_mismatch` | 75 |
| `missing_answers` | 22 |
| `empty_prediction` | 3 |

Joint-ablation failures by hop:

| Hop | Failures |
|---:|---:|
| 1-hop | 5,025 |
| 2-hop | 2,055 |
| 3-hop | 10,982 |

## Interpretation

The two capabilities address different error sources:

1. Exact typed entity linking controls the starting candidate set across all
   path lengths.
2. The start-revisit constraint controls cyclic expansion inside selected
   3-hop routes.

Their effects are complementary but not linearly additive because fuzzy start
candidate expansion changes which cyclic paths are reached. The 28 local gains
under the joint ablation are accidental cancellations between two incorrect
behaviors; the joint configuration does not correct any question that is
incorrect in Full.

The results support keeping both behaviors configurable in the unified Core and
selecting them through domain adapters and route specifications.

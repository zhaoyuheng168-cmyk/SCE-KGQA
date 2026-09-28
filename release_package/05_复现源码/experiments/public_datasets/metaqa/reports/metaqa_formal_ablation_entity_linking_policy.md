# MetaQA Formal Ablation: Entity-Linking Policy

## Scope

- Dataset split: MetaQA test.
- Questions: **39,093**.
- Setting: **Oracle-qtype typed-path execution**, not end-to-end route prediction.
- Compared configurations differ only in entity-linking policy.
- Both configurations retain the start-revisit constraint and final
  start-entity answer policy.

MetaQA explicitly marks the topic entity in square brackets. The Full
configuration therefore uses exact typed linking, while the ablation replaces
it with substring-based fuzzy typed linking.

## Overall Results

| Configuration | Exact | Accuracy | Macro precision | Macro recall | Macro F1 |
|---|---:|---:|---:|---:|---:|
| Full: exact typed linking | 38,553 / 39,093 | 98.619% | 99.297% | 99.997% | 99.511% |
| Fuzzy typed linking | 24,050 / 39,093 | 61.520% | 77.523% | 99.802% | 82.303% |
| Difference | -14,503 | -37.100 pp | -21.774 pp | -0.195 pp | -17.208 pp |

## Results by Hop

| Hop | Full accuracy | Fuzzy accuracy | Difference |
|---:|---:|---:|---:|
| 1-hop | 94.571% | 49.482% | -45.089 pp |
| 2-hop | 100.000% | 86.182% | -13.818 pp |
| 3-hop | 100.000% | 44.213% | -55.787 pp |

## Paired Per-Question Comparison

- Questions correct in Full but incorrect with fuzzy linking: **14,503**.
- Questions incorrect in Full but correct with fuzzy linking: **0**.
- Questions incorrect in both configurations: **540**.

New failures introduced by fuzzy linking:

| Failure type | Count |
|---|---:|
| `over_return` | 14,220 |
| `mixed_answer_mismatch` | 192 |
| `missing_answers` | 72 |
| `empty_prediction` | 19 |

## Subject-Role Distribution of Newly Incorrect Questions

| Starting role | Newly incorrect |
|---|---:|
| Movie | 13,906 |
| Tag | 385 |
| Actor | 160 |
| Writer | 34 |
| Director | 18 |

Substring matching is especially harmful for movie titles because short or
overlapping titles expand to multiple typed start candidates. The resulting
paths are graph-valid but answer different entity interpretations than the
benchmark's explicitly bracketed topic entity.

## Runtime

| Configuration | Total runtime |
|---|---:|
| Exact typed linking | 3.962 seconds |
| Fuzzy typed linking | 188.160 seconds |
| Slowdown | **47.49x** |

Exact typed linking uses direct typed lookup. Fuzzy typed linking scans and
expands candidate entities, increasing both execution cost and answer noise.

## Interpretation

This ablation supports a domain-configurable entity-linking policy:

- Public benchmarks with explicit topic entities should use `exact_typed`.
- Real industrial questions may require `fuzzy_typed` candidate generation,
  followed by ranking or validation.

The result does not claim that exact matching is universally superior. It shows
that hard-coding one entity-linking policy into the shared Core is unsuitable
across domains.

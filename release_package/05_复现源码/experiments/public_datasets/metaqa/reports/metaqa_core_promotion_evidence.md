# MetaQA Unified-Core Promotion Evidence

## Scope

- Bounded coverage smoke: at most 3 test questions per qtype.
- This is evidence for core-promotion decisions, not a formal benchmark result.
- Both runs use the same questions, typed routes, and raw knowledge base.

## Before and After

| Configuration | Exact | Accuracy | Failure counts |
|---|---:|---:|---|
| Before: fuzzy typed linking | 101/141 | 0.7163 | `{'none': 101, 'over_return': 39, 'mixed_answer_mismatch': 1}` |
| After: exact typed linking | 139/141 | 0.9858 | `{'none': 139, 'over_return': 2}` |

- Corrected questions: **38**
- Regressed questions: **0**
- Remaining failures: **2**

## Results by Hop

| Hop | Before exact | After exact | Delta |
|---:|---:|---:|---:|
| 1 | 17/33 | 31/33 | +14 |
| 2 | 59/63 | 63/63 | +4 |
| 3 | 25/45 | 45/45 | +20 |

## Remaining Failures

| Qtype | Subject | Predicted | Gold | Failure |
|---|---|---|---|---|
| `movie_to_writer` | `Molière` | `['Ariane Mnouchkine', 'Grégoire Vigneron', 'Laurent Tirard']` | `['Ariane Mnouchkine']` | `over_return` |
| `movie_to_year` | `The Man Who Laughs` | `['2012', '1928']` | `['2012']` | `over_return` |

## Interpretation

The configurable entity-linking policy corrected all 38 failures caused by substring-expanded subject candidates and introduced no regressions. The two remaining failures are same-string entity collisions in the raw MetaQA graph.

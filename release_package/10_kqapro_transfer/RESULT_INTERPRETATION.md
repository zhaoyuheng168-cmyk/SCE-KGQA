# Result Interpretation

## Frozen Main Comparison

- BART top-1: `90.485%`
- Schema-only reranking: `89.809%`
- Execution feedback + non-empty constraint: `93.802%`
- Pre-registered SCE full: `93.220%`

## What Worked

Execution success and non-empty-answer feedback produced the largest and most
consistent gain. Compared with BART top-1, the strongest variant improved:

- compositional: `95.763% -> 97.009%`
- multihop: `87.729% -> 91.691%`
- multihop compositional: `90.211% -> 93.355%`
- qualifier/evidence: `84.078% -> 89.825%`
- simple/attribute: `95.197% -> 97.126%`
- verification: `90.203% -> 93.772%`

## Negative Results

Schema-only reranking reduced exact match. Schema legality is not sufficient
to determine semantic relevance: a program may use valid entities, relations
and attributes while still expressing the wrong intent.

Question relevance also reduced the full configuration in this frozen setup.
The lexical overlap feature can prefer superficially similar but semantically
incorrect arguments.

These results must not be hidden. The defensible conclusion is that
execution-aware candidate validation transfers robustly, while Schema and
lexical relevance require better calibration.

## Remaining Errors

The pre-registered full method has 793 incorrect questions:

| Error type | Count | Share |
|---|---:|---:|
| Execution error | 340 | 42.875% |
| Program argument error | 210 | 26.482% |
| Empty execution result | 120 | 15.132% |
| Program structure error | 117 | 14.754% |
| Relation direction error | 6 | 0.757% |

This taxonomy is heuristic and should be described as automatic error
classification, not manual adjudication.

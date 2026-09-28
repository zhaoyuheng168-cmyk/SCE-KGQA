# MetaQA Formal Predicted-Route Evaluation: Template Holdout

## Scope

- Source data: MetaQA train split.
- Split method: deterministic per-qtype template holdout.
- Held-out fraction: **20%**.
- Training questions: **263,065**.
- Evaluation questions: **66,217**.
- Training templates: **416**.
- Held-out evaluation templates: **105**.
- Train/evaluation template overlap: **0**.
- Topic entity text is masked before route classification.

This setting evaluates natural-language route prediction and unified-Core answer
execution on question templates that are absent from classifier training.

## Overall Results

| Metric | Result |
|---|---:|
| Route accuracy | **55,110 / 66,217 = 83.226%** |
| End-to-end answer Exact Match | **54,638 / 66,217 = 82.514%** |
| End-to-end macro F1 | **84.090%** |

## Results by Hop

| Hop | Questions | Route accuracy | Answer Exact Match | Macro F1 |
|---:|---:|---:|---:|---:|
| 1-hop | 19,591 | 82.477% | 79.307% | 82.398% |
| 2-hop | 23,781 | 98.680% | 98.696% | 98.711% |
| 3-hop | 22,845 | 67.783% | 68.418% | 70.322% |

## Error Propagation

| Route outcome | Questions | Answer exact |
|---|---:|---:|
| Route correct | 55,110 | 54,273 |
| Route incorrect | 11,107 | 365 |

When the predicted route is correct, remaining answer errors primarily reflect
known raw-graph ambiguity. When the route is incorrect, answer correctness is
rare and usually results from different paths producing the same answer set.

## Largest Route Confusions

| Gold qtype | Predicted qtype | Count |
|---|---|---:|
| `movie_to_director_to_movie_to_genre` | `movie_to_director_to_movie_to_writer` | 1,683 |
| `movie_to_actor_to_movie_to_language` | `movie_to_actor_to_movie_to_genre` | 1,476 |
| `movie_to_actor_to_movie_to_writer` | `movie_to_actor_to_movie_to_director` | 946 |
| `movie_to_actor_to_movie_to_director` | `movie_to_actor_to_movie_to_year` | 901 |
| `movie_to_director` | `actor_to_movie_to_director` | 892 |
| `actor_to_movie` | `movie_to_actor_to_movie` | 861 |
| `movie_to_writer_to_movie_to_director` | `movie_to_writer_to_movie_to_genre` | 691 |
| `movie_to_writer_to_movie_to_actor` | `movie_to_director_to_movie_to_actor` | 666 |
| `movie_to_writer_to_movie_to_director` | `movie_to_writer_to_movie_to_year` | 665 |
| `movie_to_writer` | `movie_to_director` | 624 |

## Runtime

| Stage | Seconds |
|---|---:|
| Route-classifier training | 1,164.922 |
| Route prediction | 1.612 |
| Graph loading | 1.343 |
| Answer execution | 3.554 |
| Total | 1,173.067 |

## Interpretation

The result removes the Oracle-qtype assumption and demonstrates that the same
unified Core can execute predicted routes end to end. Performance is no longer
artificially saturated:

- 2-hop unseen-template routes generalize strongly.
- 1-hop performance is moderate.
- 3-hop route prediction is the main language-understanding bottleneck.

This is a supervised in-domain template-generalization experiment. It does not
claim zero-shot transfer from the Gansu domain to MetaQA language.

## Remaining Validation

The current result uses one deterministic template partition. A stronger paper
result should repeat the template-held-out evaluation across multiple
partitions and report mean and standard deviation.

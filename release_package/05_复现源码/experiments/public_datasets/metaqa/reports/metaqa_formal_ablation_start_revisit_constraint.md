# MetaQA Formal Ablation: Start-Entity Revisit Constraint

## Scope

- Dataset split: MetaQA test.
- Questions: **39,093**.
- Setting: **Oracle-qtype typed-path execution**, not end-to-end route prediction.
- Compared configurations differ only in the intermediate start-entity revisit
  constraint.
- Both configurations use exact typed entity linking and the same final
  start-entity answer policy.

## Overall Results

| Configuration | Exact | Accuracy | Macro F1 |
|---|---:|---:|---:|
| Full unified Core | 38,553 / 39,093 | 98.619% | 99.511% |
| Without start-revisit constraint | 31,878 / 39,093 | 81.544% | 97.360% |
| Difference | -6,675 | -17.075 pp | -2.151 pp |

## Results by Hop

| Hop | Full accuracy | Without constraint | Difference |
|---:|---:|---:|---:|
| 1-hop | 94.571% | 94.571% | 0.000 pp |
| 2-hop | 100.000% | 100.000% | 0.000 pp |
| 3-hop | 100.000% | 53.237% | -46.763 pp |

## Paired Per-Question Comparison

- Questions correct in Full but incorrect without constraint: **6,675**.
- Questions incorrect in Full but correct without constraint: **0**.
- All **6,675** newly introduced failures are `over_return`.
- All **6,675** newly introduced failures occur in 3-hop cyclic routes.

The ablated executor revisits the starting movie at the second path step and
therefore returns properties of the starting movie in addition to the intended
other movies.

## Affected Qtypes

| Qtype | Newly incorrect |
|---|---:|
| `movie_to_director_to_movie_to_year` | 976 |
| `movie_to_director_to_movie_to_actor` | 791 |
| `movie_to_actor_to_movie_to_writer` | 743 |
| `movie_to_writer_to_movie_to_year` | 706 |
| `movie_to_actor_to_movie_to_director` | 696 |
| `movie_to_writer_to_movie_to_actor` | 636 |
| `movie_to_director_to_movie_to_writer` | 548 |
| `movie_to_actor_to_movie_to_year` | 489 |
| `movie_to_writer_to_movie_to_director` | 374 |
| `movie_to_director_to_movie_to_genre` | 240 |
| `movie_to_writer_to_movie_to_genre` | 215 |
| `movie_to_actor_to_movie_to_genre` | 163 |
| `movie_to_actor_to_movie_to_language` | 38 |
| `movie_to_director_to_movie_to_language` | 33 |
| `movie_to_writer_to_movie_to_language` | 27 |

## Interpretation

The result isolates the contribution of the domain-independent typed-path
constraint:

```python
PathConstraints(exclude_start_at_steps=(2,))
```

The constraint has no effect on unrelated 1-hop and 2-hop routes, while it
prevents systematic over-return on cyclic 3-hop routes. This is evidence for a
reusable execution capability, rather than a movie-domain answer filter.

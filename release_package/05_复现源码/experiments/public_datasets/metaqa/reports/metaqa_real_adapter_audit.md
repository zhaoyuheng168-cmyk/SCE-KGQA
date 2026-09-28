# Real MetaQA Unified-Core Adapter Audit

- Raw directory: `/root/work/GansuTechFinance_KGQA_RELEASE_RUNTIME/deliverables/paper_submission_system_20260522_114215/experiments/public_datasets/metaqa/raw/dataset/MetaQA_clean`
- Adapter: `metaqa_real`
- Raw unique qtypes: **49**
- Adapter routes: **49**
- Raw relations: **9**
- Adapter relations: **9**
- Schema validation issues: **0**
- Conclusion: **PASS**

## Coverage

| Item | Missing from adapter | Extra in adapter |
|---|---:|---:|
| Qtypes | 0 | 0 |
| Relations | 0 | 0 |

## Routes by Hop

| Hop | Raw qtypes | Adapter routes |
|---:|---:|---:|
| 1 | 13 | 13 |
| 2 | 21 | 21 |
| 3 | 15 | 15 |

## Automatically Constrained Routes

| Qtype | Exclude start at steps |
|---|---|
| `movie_to_actor_to_movie_to_director` | `[2]` |
| `movie_to_actor_to_movie_to_genre` | `[2]` |
| `movie_to_actor_to_movie_to_language` | `[2]` |
| `movie_to_actor_to_movie_to_writer` | `[2]` |
| `movie_to_actor_to_movie_to_year` | `[2]` |
| `movie_to_director_to_movie_to_actor` | `[2]` |
| `movie_to_director_to_movie_to_genre` | `[2]` |
| `movie_to_director_to_movie_to_language` | `[2]` |
| `movie_to_director_to_movie_to_writer` | `[2]` |
| `movie_to_director_to_movie_to_year` | `[2]` |
| `movie_to_writer_to_movie_to_actor` | `[2]` |
| `movie_to_writer_to_movie_to_director` | `[2]` |
| `movie_to_writer_to_movie_to_genre` | `[2]` |
| `movie_to_writer_to_movie_to_language` | `[2]` |
| `movie_to_writer_to_movie_to_year` | `[2]` |

## Errors

- None.

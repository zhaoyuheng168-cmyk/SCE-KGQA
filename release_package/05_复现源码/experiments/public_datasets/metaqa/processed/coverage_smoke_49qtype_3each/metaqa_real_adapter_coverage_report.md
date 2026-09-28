# Real MetaQA Unified-Core Coverage Smoke

- This is a bounded coverage smoke, not a formal evaluation.
- Limit per qtype: **3**
- Qtypes covered: **47/49**
- Questions executed: **141/147 maximum**
- Exact matches: **101/141**
- Distinct failures: **2**

## Failure Counts

- `mixed_answer_mismatch`: 1
- `none`: 101
- `over_return`: 39

## Per-Qtype Summary

| Hop | Qtype | Selected | Exact | Failures |
|---:|---|---:|---:|---|
| 1 | `actor_to_movie` | 3 | 3 | `{'none': 3}` |
| 1 | `director_to_movie` | 3 | 3 | `{'none': 3}` |
| 1 | `movie_to_actor` | 3 | 2 | `{'none': 2, 'over_return': 1}` |
| 1 | `movie_to_director` | 3 | 1 | `{'over_return': 2, 'none': 1}` |
| 1 | `movie_to_genre` | 3 | 2 | `{'none': 2, 'over_return': 1}` |
| 1 | `movie_to_imdbrating` | 0 | 0 | `{}` |
| 1 | `movie_to_imdbvotes` | 0 | 0 | `{}` |
| 1 | `movie_to_language` | 3 | 3 | `{'none': 3}` |
| 1 | `movie_to_tags` | 3 | 0 | `{'over_return': 3}` |
| 1 | `movie_to_writer` | 3 | 1 | `{'over_return': 2, 'none': 1}` |
| 1 | `movie_to_year` | 3 | 0 | `{'over_return': 3}` |
| 1 | `tag_to_movie` | 3 | 0 | `{'over_return': 3}` |
| 1 | `writer_to_movie` | 3 | 2 | `{'none': 2, 'over_return': 1}` |
| 2 | `actor_to_movie_to_actor` | 3 | 2 | `{'over_return': 1, 'none': 2}` |
| 2 | `actor_to_movie_to_director` | 3 | 3 | `{'none': 3}` |
| 2 | `actor_to_movie_to_genre` | 3 | 3 | `{'none': 3}` |
| 2 | `actor_to_movie_to_language` | 3 | 3 | `{'none': 3}` |
| 2 | `actor_to_movie_to_writer` | 3 | 3 | `{'none': 3}` |
| 2 | `actor_to_movie_to_year` | 3 | 3 | `{'none': 3}` |
| 2 | `director_to_movie_to_actor` | 3 | 3 | `{'none': 3}` |
| 2 | `director_to_movie_to_director` | 3 | 3 | `{'none': 3}` |
| 2 | `director_to_movie_to_genre` | 3 | 3 | `{'none': 3}` |
| 2 | `director_to_movie_to_language` | 3 | 3 | `{'none': 3}` |
| 2 | `director_to_movie_to_writer` | 3 | 3 | `{'none': 3}` |
| 2 | `director_to_movie_to_year` | 3 | 3 | `{'none': 3}` |
| 2 | `movie_to_actor_to_movie` | 3 | 1 | `{'over_return': 2, 'none': 1}` |
| 2 | `movie_to_director_to_movie` | 3 | 3 | `{'none': 3}` |
| 2 | `movie_to_writer_to_movie` | 3 | 2 | `{'none': 2, 'over_return': 1}` |
| 2 | `writer_to_movie_to_actor` | 3 | 3 | `{'none': 3}` |
| 2 | `writer_to_movie_to_director` | 3 | 3 | `{'none': 3}` |
| 2 | `writer_to_movie_to_genre` | 3 | 3 | `{'none': 3}` |
| 2 | `writer_to_movie_to_language` | 3 | 3 | `{'none': 3}` |
| 2 | `writer_to_movie_to_writer` | 3 | 3 | `{'none': 3}` |
| 2 | `writer_to_movie_to_year` | 3 | 3 | `{'none': 3}` |
| 3 | `movie_to_actor_to_movie_to_director` | 3 | 2 | `{'none': 2, 'over_return': 1}` |
| 3 | `movie_to_actor_to_movie_to_genre` | 3 | 2 | `{'none': 2, 'over_return': 1}` |
| 3 | `movie_to_actor_to_movie_to_language` | 3 | 3 | `{'none': 3}` |
| 3 | `movie_to_actor_to_movie_to_writer` | 3 | 3 | `{'none': 3}` |
| 3 | `movie_to_actor_to_movie_to_year` | 3 | 2 | `{'none': 2, 'over_return': 1}` |
| 3 | `movie_to_director_to_movie_to_actor` | 3 | 1 | `{'over_return': 2, 'none': 1}` |
| 3 | `movie_to_director_to_movie_to_genre` | 3 | 2 | `{'over_return': 1, 'none': 2}` |
| 3 | `movie_to_director_to_movie_to_language` | 3 | 1 | `{'over_return': 2, 'none': 1}` |
| 3 | `movie_to_director_to_movie_to_writer` | 3 | 1 | `{'over_return': 2, 'none': 1}` |
| 3 | `movie_to_director_to_movie_to_year` | 3 | 1 | `{'over_return': 2, 'none': 1}` |
| 3 | `movie_to_writer_to_movie_to_actor` | 3 | 2 | `{'over_return': 1, 'none': 2}` |
| 3 | `movie_to_writer_to_movie_to_director` | 3 | 1 | `{'over_return': 2, 'none': 1}` |
| 3 | `movie_to_writer_to_movie_to_genre` | 3 | 1 | `{'none': 1, 'over_return': 2}` |
| 3 | `movie_to_writer_to_movie_to_language` | 3 | 3 | `{'none': 3}` |
| 3 | `movie_to_writer_to_movie_to_year` | 3 | 0 | `{'mixed_answer_mismatch': 1, 'over_return': 2}` |

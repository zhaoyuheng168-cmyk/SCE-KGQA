# Real MetaQA Unified-Core Coverage Smoke

- This is a bounded coverage smoke, not a formal evaluation.
- Limit per qtype: **3**
- Qtypes covered: **47/49**
- Questions executed: **141/147 maximum**
- Exact matches: **139/141**
- Distinct failures: **1**

## Failure Counts

- `none`: 139
- `over_return`: 2

## Per-Qtype Summary

| Hop | Qtype | Selected | Exact | Failures |
|---:|---|---:|---:|---|
| 1 | `actor_to_movie` | 3 | 3 | `{'none': 3}` |
| 1 | `director_to_movie` | 3 | 3 | `{'none': 3}` |
| 1 | `movie_to_actor` | 3 | 3 | `{'none': 3}` |
| 1 | `movie_to_director` | 3 | 3 | `{'none': 3}` |
| 1 | `movie_to_genre` | 3 | 3 | `{'none': 3}` |
| 1 | `movie_to_imdbrating` | 0 | 0 | `{}` |
| 1 | `movie_to_imdbvotes` | 0 | 0 | `{}` |
| 1 | `movie_to_language` | 3 | 3 | `{'none': 3}` |
| 1 | `movie_to_tags` | 3 | 3 | `{'none': 3}` |
| 1 | `movie_to_writer` | 3 | 2 | `{'over_return': 1, 'none': 2}` |
| 1 | `movie_to_year` | 3 | 2 | `{'over_return': 1, 'none': 2}` |
| 1 | `tag_to_movie` | 3 | 3 | `{'none': 3}` |
| 1 | `writer_to_movie` | 3 | 3 | `{'none': 3}` |
| 2 | `actor_to_movie_to_actor` | 3 | 3 | `{'none': 3}` |
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
| 2 | `movie_to_actor_to_movie` | 3 | 3 | `{'none': 3}` |
| 2 | `movie_to_director_to_movie` | 3 | 3 | `{'none': 3}` |
| 2 | `movie_to_writer_to_movie` | 3 | 3 | `{'none': 3}` |
| 2 | `writer_to_movie_to_actor` | 3 | 3 | `{'none': 3}` |
| 2 | `writer_to_movie_to_director` | 3 | 3 | `{'none': 3}` |
| 2 | `writer_to_movie_to_genre` | 3 | 3 | `{'none': 3}` |
| 2 | `writer_to_movie_to_language` | 3 | 3 | `{'none': 3}` |
| 2 | `writer_to_movie_to_writer` | 3 | 3 | `{'none': 3}` |
| 2 | `writer_to_movie_to_year` | 3 | 3 | `{'none': 3}` |
| 3 | `movie_to_actor_to_movie_to_director` | 3 | 3 | `{'none': 3}` |
| 3 | `movie_to_actor_to_movie_to_genre` | 3 | 3 | `{'none': 3}` |
| 3 | `movie_to_actor_to_movie_to_language` | 3 | 3 | `{'none': 3}` |
| 3 | `movie_to_actor_to_movie_to_writer` | 3 | 3 | `{'none': 3}` |
| 3 | `movie_to_actor_to_movie_to_year` | 3 | 3 | `{'none': 3}` |
| 3 | `movie_to_director_to_movie_to_actor` | 3 | 3 | `{'none': 3}` |
| 3 | `movie_to_director_to_movie_to_genre` | 3 | 3 | `{'none': 3}` |
| 3 | `movie_to_director_to_movie_to_language` | 3 | 3 | `{'none': 3}` |
| 3 | `movie_to_director_to_movie_to_writer` | 3 | 3 | `{'none': 3}` |
| 3 | `movie_to_director_to_movie_to_year` | 3 | 3 | `{'none': 3}` |
| 3 | `movie_to_writer_to_movie_to_actor` | 3 | 3 | `{'none': 3}` |
| 3 | `movie_to_writer_to_movie_to_director` | 3 | 3 | `{'none': 3}` |
| 3 | `movie_to_writer_to_movie_to_genre` | 3 | 3 | `{'none': 3}` |
| 3 | `movie_to_writer_to_movie_to_language` | 3 | 3 | `{'none': 3}` |
| 3 | `movie_to_writer_to_movie_to_year` | 3 | 3 | `{'none': 3}` |

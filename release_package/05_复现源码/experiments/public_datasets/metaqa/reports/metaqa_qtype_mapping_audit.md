# MetaQA Qtype to Typed-Path Mapping Audit

- Raw directory: `/root/work/GansuTechFinance_KGQA_RELEASE_RUNTIME/deliverables/paper_submission_system_20260522_114215/experiments/public_datasets/metaqa/raw/dataset/MetaQA_clean`
- Unique qtypes: **49**
- Mapping errors: **0**
- Conclusion: **PASS**

## Summary

| Hop | Unique qtypes | Total aligned QA/qtype rows |
|---:|---:|---:|
| 1 | 13 | 116045 |
| 2 | 21 | 148724 |
| 3 | 15 | 142744 |

## Generated Typed Paths

| Hop | Qtype | Count | Typed path |
|---:|---|---:|---|
| 1 | `actor_to_movie` | 10273 | `actor -[starred_actors / in]-> movie` |
| 1 | `director_to_movie` | 6221 | `director -[directed_by / in]-> movie` |
| 1 | `movie_to_actor` | 13565 | `movie -[starred_actors / out]-> actor` |
| 1 | `movie_to_director` | 15234 | `movie -[directed_by / out]-> director` |
| 1 | `movie_to_genre` | 12483 | `movie -[has_genre / out]-> genre` |
| 1 | `movie_to_imdbrating` | 292 | `movie -[has_imdb_rating / out]-> imdbrating` |
| 1 | `movie_to_imdbvotes` | 110 | `movie -[has_imdb_votes / out]-> imdbvotes` |
| 1 | `movie_to_language` | 3174 | `movie -[in_language / out]-> language` |
| 1 | `movie_to_tags` | 9697 | `movie -[has_tags / out]-> tags` |
| 1 | `movie_to_writer` | 13130 | `movie -[written_by / out]-> writer` |
| 1 | `movie_to_year` | 16726 | `movie -[release_year / out]-> year` |
| 1 | `tag_to_movie` | 4621 | `tag -[has_tags / in]-> movie` |
| 1 | `writer_to_movie` | 10519 | `writer -[written_by / in]-> movie` |
| 2 | `actor_to_movie_to_actor` | 9574 | `actor -[starred_actors / in]-> movie ; movie -[starred_actors / out]-> actor` |
| 2 | `actor_to_movie_to_director` | 9241 | `actor -[starred_actors / in]-> movie ; movie -[directed_by / out]-> director` |
| 2 | `actor_to_movie_to_genre` | 8548 | `actor -[starred_actors / in]-> movie ; movie -[has_genre / out]-> genre` |
| 2 | `actor_to_movie_to_language` | 3067 | `actor -[starred_actors / in]-> movie ; movie -[in_language / out]-> language` |
| 2 | `actor_to_movie_to_writer` | 8499 | `actor -[starred_actors / in]-> movie ; movie -[written_by / out]-> writer` |
| 2 | `actor_to_movie_to_year` | 10072 | `actor -[starred_actors / in]-> movie ; movie -[release_year / out]-> year` |
| 2 | `director_to_movie_to_actor` | 4800 | `director -[directed_by / in]-> movie ; movie -[starred_actors / out]-> actor` |
| 2 | `director_to_movie_to_director` | 1797 | `director -[directed_by / in]-> movie ; movie -[directed_by / out]-> director` |
| 2 | `director_to_movie_to_genre` | 5205 | `director -[directed_by / in]-> movie ; movie -[has_genre / out]-> genre` |
| 2 | `director_to_movie_to_language` | 1850 | `director -[directed_by / in]-> movie ; movie -[in_language / out]-> language` |
| 2 | `director_to_movie_to_writer` | 3688 | `director -[directed_by / in]-> movie ; movie -[written_by / out]-> writer` |
| 2 | `director_to_movie_to_year` | 6026 | `director -[directed_by / in]-> movie ; movie -[release_year / out]-> year` |
| 2 | `movie_to_actor_to_movie` | 11709 | `movie -[starred_actors / out]-> actor ; actor -[starred_actors / in]-> movie` |
| 2 | `movie_to_director_to_movie` | 11412 | `movie -[directed_by / out]-> director ; director -[directed_by / in]-> movie` |
| 2 | `movie_to_writer_to_movie` | 8817 | `movie -[written_by / out]-> writer ; writer -[written_by / in]-> movie` |
| 2 | `writer_to_movie_to_actor` | 8447 | `writer -[written_by / in]-> movie ; movie -[starred_actors / out]-> actor` |
| 2 | `writer_to_movie_to_director` | 7342 | `writer -[written_by / in]-> movie ; movie -[directed_by / out]-> director` |
| 2 | `writer_to_movie_to_genre` | 8633 | `writer -[written_by / in]-> movie ; movie -[has_genre / out]-> genre` |
| 2 | `writer_to_movie_to_language` | 2629 | `writer -[written_by / in]-> movie ; movie -[in_language / out]-> language` |
| 2 | `writer_to_movie_to_writer` | 7142 | `writer -[written_by / in]-> movie ; movie -[written_by / out]-> writer` |
| 2 | `writer_to_movie_to_year` | 10226 | `writer -[written_by / in]-> movie ; movie -[release_year / out]-> year` |
| 3 | `movie_to_actor_to_movie_to_director` | 11600 | `movie -[starred_actors / out]-> actor ; actor -[starred_actors / in]-> movie ; movie -[directed_by / out]-> director` |
| 3 | `movie_to_actor_to_movie_to_genre` | 11513 | `movie -[starred_actors / out]-> actor ; actor -[starred_actors / in]-> movie ; movie -[has_genre / out]-> genre` |
| 3 | `movie_to_actor_to_movie_to_language` | 8735 | `movie -[starred_actors / out]-> actor ; actor -[starred_actors / in]-> movie ; movie -[in_language / out]-> language` |
| 3 | `movie_to_actor_to_movie_to_writer` | 11516 | `movie -[starred_actors / out]-> actor ; actor -[starred_actors / in]-> movie ; movie -[written_by / out]-> writer` |
| 3 | `movie_to_actor_to_movie_to_year` | 11688 | `movie -[starred_actors / out]-> actor ; actor -[starred_actors / in]-> movie ; movie -[release_year / out]-> year` |
| 3 | `movie_to_director_to_movie_to_actor` | 10784 | `movie -[directed_by / out]-> director ; director -[directed_by / in]-> movie ; movie -[starred_actors / out]-> actor` |
| 3 | `movie_to_director_to_movie_to_genre` | 10822 | `movie -[directed_by / out]-> director ; director -[directed_by / in]-> movie ; movie -[has_genre / out]-> genre` |
| 3 | `movie_to_director_to_movie_to_language` | 5909 | `movie -[directed_by / out]-> director ; director -[directed_by / in]-> movie ; movie -[in_language / out]-> language` |
| 3 | `movie_to_director_to_movie_to_writer` | 11005 | `movie -[directed_by / out]-> director ; director -[directed_by / in]-> movie ; movie -[written_by / out]-> writer` |
| 3 | `movie_to_director_to_movie_to_year` | 11350 | `movie -[directed_by / out]-> director ; director -[directed_by / in]-> movie ; movie -[release_year / out]-> year` |
| 3 | `movie_to_writer_to_movie_to_actor` | 8216 | `movie -[written_by / out]-> writer ; writer -[written_by / in]-> movie ; movie -[starred_actors / out]-> actor` |
| 3 | `movie_to_writer_to_movie_to_director` | 8734 | `movie -[written_by / out]-> writer ; writer -[written_by / in]-> movie ; movie -[directed_by / out]-> director` |
| 3 | `movie_to_writer_to_movie_to_genre` | 8212 | `movie -[written_by / out]-> writer ; writer -[written_by / in]-> movie ; movie -[has_genre / out]-> genre` |
| 3 | `movie_to_writer_to_movie_to_language` | 3908 | `movie -[written_by / out]-> writer ; writer -[written_by / in]-> movie ; movie -[in_language / out]-> language` |
| 3 | `movie_to_writer_to_movie_to_year` | 8752 | `movie -[written_by / out]-> writer ; writer -[written_by / in]-> movie ; movie -[release_year / out]-> year` |

## Errors

- None.

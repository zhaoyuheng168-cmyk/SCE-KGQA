# MetaQA movie_to_actor_to_movie_to_genre 10-Question Execution Smoke

- Hop: **3**
- Split: **test**
- Questions executed: **10**
- Exact matches: **9/10**
- KB malformed lines observed: **0**
- Typed path: `[{"source_role": "movie", "relation": "starred_actors", "target_role": "actor", "direction": "out"}, {"source_role": "actor", "relation": "starred_actors", "target_role": "movie", "direction": "in"}, {"source_role": "movie", "relation": "has_genre", "target_role": "genre", "direction": "out"}]`
- Exclude start at steps: **[]**
- Conclusion: **FAIL**

## Failure Counts

- `answer_set_mismatch`: 1
- `none`: 9

| QID | Subject | Frontier sizes | Excluded revisits | Predicted count | Gold count | Exact | Failure |
|---|---|---|---|---:|---:|---:|---|
| `metaqa_3hop_test_movie_to_actor_to_movie_to_genre_000015` | Trog | [1, 39, 44] | [0, 0, 0] | 8 | 8 | True |  |
| `metaqa_3hop_test_movie_to_actor_to_movie_to_genre_000020` | Scarface | [8, 99, 128] | [0, 0, 0] | 17 | 17 | True |  |
| `metaqa_3hop_test_movie_to_actor_to_movie_to_genre_000037` | The 40-Year-Old Virgin | [1, 16, 25] | [0, 0, 0] | 5 | 5 | True |  |
| `metaqa_3hop_test_movie_to_actor_to_movie_to_genre_000045` | Julie | [1, 31, 40] | [0, 0, 0] | 8 | 8 | True |  |
| `metaqa_3hop_test_movie_to_actor_to_movie_to_genre_000046` | 22 Jump Street | [2, 29, 48] | [0, 0, 0] | 10 | 10 | True |  |
| `metaqa_3hop_test_movie_to_actor_to_movie_to_genre_000055` | City of Hope | [3, 21, 20] | [0, 0, 0] | 7 | 7 | True |  |
| `metaqa_3hop_test_movie_to_actor_to_movie_to_genre_000071` | The 'Human' Factor | [2, 27, 19] | [0, 0, 0] | 10 | 10 | True |  |
| `metaqa_3hop_test_movie_to_actor_to_movie_to_genre_000097` | Walk the Line | [4, 54, 72] | [0, 0, 0] | 15 | 14 | False | answer_set_mismatch |
| `metaqa_3hop_test_movie_to_actor_to_movie_to_genre_000113` | Tuff Turf | [2, 25, 16] | [0, 0, 0] | 6 | 6 | True |  |
| `metaqa_3hop_test_movie_to_actor_to_movie_to_genre_000119` | The Spirit | [2, 7, 4] | [0, 0, 0] | 4 | 4 | True |  |

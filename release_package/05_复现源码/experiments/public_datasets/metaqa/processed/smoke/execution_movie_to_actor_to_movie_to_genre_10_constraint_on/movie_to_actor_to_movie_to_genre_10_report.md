# MetaQA movie_to_actor_to_movie_to_genre 10-Question Execution Smoke

- Hop: **3**
- Split: **test**
- Questions executed: **10**
- Exact matches: **10/10**
- KB malformed lines observed: **0**
- Typed path: `[{"source_role": "movie", "relation": "starred_actors", "target_role": "actor", "direction": "out"}, {"source_role": "actor", "relation": "starred_actors", "target_role": "movie", "direction": "in"}, {"source_role": "movie", "relation": "has_genre", "target_role": "genre", "direction": "out"}]`
- Exclude start at steps: **[2]**
- Conclusion: **PASS**

## Failure Counts

- `none`: 10

| QID | Subject | Frontier sizes | Excluded revisits | Predicted count | Gold count | Exact | Failure |
|---|---|---|---|---:|---:|---:|---|
| `metaqa_3hop_test_movie_to_actor_to_movie_to_genre_000015` | Trog | [1, 38, 43] | [0, 1, 0] | 8 | 8 | True |  |
| `metaqa_3hop_test_movie_to_actor_to_movie_to_genre_000020` | Scarface | [8, 91, 104] | [0, 8, 0] | 17 | 17 | True |  |
| `metaqa_3hop_test_movie_to_actor_to_movie_to_genre_000037` | The 40-Year-Old Virgin | [1, 15, 24] | [0, 1, 0] | 5 | 5 | True |  |
| `metaqa_3hop_test_movie_to_actor_to_movie_to_genre_000045` | Julie | [1, 30, 40] | [0, 1, 0] | 8 | 8 | True |  |
| `metaqa_3hop_test_movie_to_actor_to_movie_to_genre_000046` | 22 Jump Street | [2, 27, 46] | [0, 2, 0] | 10 | 10 | True |  |
| `metaqa_3hop_test_movie_to_actor_to_movie_to_genre_000055` | City of Hope | [3, 18, 17] | [0, 3, 0] | 7 | 7 | True |  |
| `metaqa_3hop_test_movie_to_actor_to_movie_to_genre_000071` | The 'Human' Factor | [2, 25, 19] | [0, 2, 0] | 10 | 10 | True |  |
| `metaqa_3hop_test_movie_to_actor_to_movie_to_genre_000097` | Walk the Line | [4, 50, 64] | [0, 4, 0] | 14 | 14 | True |  |
| `metaqa_3hop_test_movie_to_actor_to_movie_to_genre_000113` | Tuff Turf | [2, 23, 14] | [0, 2, 0] | 6 | 6 | True |  |
| `metaqa_3hop_test_movie_to_actor_to_movie_to_genre_000119` | The Spirit | [2, 5, 4] | [0, 2, 0] | 4 | 4 | True |  |

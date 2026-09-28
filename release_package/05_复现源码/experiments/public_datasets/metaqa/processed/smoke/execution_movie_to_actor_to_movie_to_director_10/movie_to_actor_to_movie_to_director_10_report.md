# MetaQA movie_to_actor_to_movie_to_director 10-Question Execution Smoke

- Hop: **3**
- Split: **test**
- Questions executed: **10**
- Exact matches: **3/10**
- KB malformed lines observed: **0**
- Typed path: `[{"source_role": "movie", "relation": "starred_actors", "target_role": "actor", "direction": "out"}, {"source_role": "actor", "relation": "starred_actors", "target_role": "movie", "direction": "in"}, {"source_role": "movie", "relation": "directed_by", "target_role": "director", "direction": "out"}]`
- Conclusion: **FAIL**

## Failure Counts

- `answer_set_mismatch`: 7
- `none`: 3

| QID | Subject | Frontier sizes | Predicted count | Gold count | Exact | Failure |
|---|---|---|---:|---:|---:|---|
| `metaqa_3hop_test_movie_to_actor_to_movie_to_director_000004` | The Inner Circle | [2, 29, 30] | 30 | 30 | True |  |
| `metaqa_3hop_test_movie_to_actor_to_movie_to_director_000011` | Buchanan Rides Alone | [3, 43, 40] | 29 | 29 | True |  |
| `metaqa_3hop_test_movie_to_actor_to_movie_to_director_000023` | The Birdcage | [4, 108, 116] | 100 | 99 | False | answer_set_mismatch |
| `metaqa_3hop_test_movie_to_actor_to_movie_to_director_000036` | Kid Millions | [1, 3, 2] | 2 | 1 | False | answer_set_mismatch |
| `metaqa_3hop_test_movie_to_actor_to_movie_to_director_000049` | Candleshoe | [4, 58, 57] | 52 | 52 | True |  |
| `metaqa_3hop_test_movie_to_actor_to_movie_to_director_000052` | Common | [3, 12, 14] | 12 | 11 | False | answer_set_mismatch |
| `metaqa_3hop_test_movie_to_actor_to_movie_to_director_000058` | Belle Starr | [4, 84, 85] | 56 | 55 | False | answer_set_mismatch |
| `metaqa_3hop_test_movie_to_actor_to_movie_to_director_000085` | Solo | [4, 14, 20] | 13 | 11 | False | answer_set_mismatch |
| `metaqa_3hop_test_movie_to_actor_to_movie_to_director_000087` | Bébé's Kids | [3, 7, 7] | 5 | 4 | False | answer_set_mismatch |
| `metaqa_3hop_test_movie_to_actor_to_movie_to_director_000102` | Strapped | [1, 5, 5] | 5 | 4 | False | answer_set_mismatch |

# MetaQA movie_to_actor_to_movie_to_director 10-Question Execution Smoke

- Hop: **3**
- Split: **test**
- Questions executed: **10**
- Exact matches: **10/10**
- KB malformed lines observed: **0**
- Typed path: `[{"source_role": "movie", "relation": "starred_actors", "target_role": "actor", "direction": "out"}, {"source_role": "actor", "relation": "starred_actors", "target_role": "movie", "direction": "in"}, {"source_role": "movie", "relation": "directed_by", "target_role": "director", "direction": "out"}]`
- Exclude start at steps: **[2]**
- Conclusion: **PASS**

## Failure Counts

- `none`: 10

| QID | Subject | Frontier sizes | Excluded revisits | Predicted count | Gold count | Exact | Failure |
|---|---|---|---|---:|---:|---:|---|
| `metaqa_3hop_test_movie_to_actor_to_movie_to_director_000004` | The Inner Circle | [2, 27, 30] | [0, 2, 0] | 30 | 30 | True |  |
| `metaqa_3hop_test_movie_to_actor_to_movie_to_director_000011` | Buchanan Rides Alone | [3, 40, 37] | [0, 3, 0] | 29 | 29 | True |  |
| `metaqa_3hop_test_movie_to_actor_to_movie_to_director_000023` | The Birdcage | [4, 104, 112] | [0, 4, 0] | 99 | 99 | True |  |
| `metaqa_3hop_test_movie_to_actor_to_movie_to_director_000036` | Kid Millions | [1, 2, 1] | [0, 1, 0] | 1 | 1 | True |  |
| `metaqa_3hop_test_movie_to_actor_to_movie_to_director_000049` | Candleshoe | [4, 54, 57] | [0, 4, 0] | 52 | 52 | True |  |
| `metaqa_3hop_test_movie_to_actor_to_movie_to_director_000052` | Common | [3, 9, 11] | [0, 3, 0] | 11 | 11 | True |  |
| `metaqa_3hop_test_movie_to_actor_to_movie_to_director_000058` | Belle Starr | [4, 80, 81] | [0, 4, 0] | 55 | 55 | True |  |
| `metaqa_3hop_test_movie_to_actor_to_movie_to_director_000085` | Solo | [4, 10, 12] | [0, 4, 0] | 11 | 11 | True |  |
| `metaqa_3hop_test_movie_to_actor_to_movie_to_director_000087` | Bébé's Kids | [3, 4, 4] | [0, 3, 0] | 4 | 4 | True |  |
| `metaqa_3hop_test_movie_to_actor_to_movie_to_director_000102` | Strapped | [1, 4, 4] | [0, 1, 0] | 4 | 4 | True |  |

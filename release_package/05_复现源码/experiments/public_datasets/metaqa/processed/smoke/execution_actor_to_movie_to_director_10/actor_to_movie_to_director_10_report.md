# MetaQA actor_to_movie_to_director 10-Question Execution Smoke

- Hop: **2**
- Split: **test**
- Questions executed: **10**
- Exact matches: **10/10**
- KB malformed lines observed: **0**
- Typed path: `[{"source_role": "actor", "relation": "starred_actors", "target_role": "movie", "direction": "in"}, {"source_role": "movie", "relation": "directed_by", "target_role": "director", "direction": "out"}]`
- Conclusion: **PASS**

## Failure Counts

- `none`: 10

| QID | Subject | Frontier sizes | Predicted count | Gold count | Exact | Failure |
|---|---|---|---:|---:|---:|---|
| `metaqa_2hop_test_actor_to_movie_to_director_000000` | John Krasinski | [6, 5] | 5 | 5 | True |  |
| `metaqa_2hop_test_actor_to_movie_to_director_000013` | Dorothy Malone | [8, 8] | 8 | 8 | True |  |
| `metaqa_2hop_test_actor_to_movie_to_director_000025` | Dave Annable | [1, 1] | 1 | 1 | True |  |
| `metaqa_2hop_test_actor_to_movie_to_director_000046` | Jane Seymour | [6, 8] | 8 | 8 | True |  |
| `metaqa_2hop_test_actor_to_movie_to_director_000048` | Brandon Quinn | [1, 1] | 1 | 1 | True |  |
| `metaqa_2hop_test_actor_to_movie_to_director_000054` | Jim Caviezel | [12, 12] | 12 | 12 | True |  |
| `metaqa_2hop_test_actor_to_movie_to_director_000056` | Margot Steinberg | [1, 1] | 1 | 1 | True |  |
| `metaqa_2hop_test_actor_to_movie_to_director_000059` | Jacqueline Pearce | [1, 1] | 1 | 1 | True |  |
| `metaqa_2hop_test_actor_to_movie_to_director_000081` | Diana Muldaur | [2, 2] | 2 | 2 | True |  |
| `metaqa_2hop_test_actor_to_movie_to_director_000125` | Linda Evans | [1, 1] | 1 | 1 | True |  |

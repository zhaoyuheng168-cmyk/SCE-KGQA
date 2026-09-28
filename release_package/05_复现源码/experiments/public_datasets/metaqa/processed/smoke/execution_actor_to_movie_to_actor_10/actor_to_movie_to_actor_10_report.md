# MetaQA actor_to_movie_to_actor 10-Question Execution Smoke

- Hop: **2**
- Split: **test**
- Questions executed: **10**
- Exact matches: **10/10**
- KB malformed lines observed: **0**
- Typed path: `[{"source_role": "actor", "relation": "starred_actors", "target_role": "movie", "direction": "in"}, {"source_role": "movie", "relation": "starred_actors", "target_role": "actor", "direction": "out"}]`
- Conclusion: **PASS**

## Failure Counts

- `none`: 10

| QID | Subject | Frontier sizes | Predicted count | Gold count | Exact | Failure |
|---|---|---|---:|---:|---:|---|
| `metaqa_2hop_test_actor_to_movie_to_actor_000006` | Angie Everhart | [1, 3] | 2 | 2 | True |  |
| `metaqa_2hop_test_actor_to_movie_to_actor_000028` | Breckin Meyer | [5, 13] | 8 | 8 | True |  |
| `metaqa_2hop_test_actor_to_movie_to_actor_000035` | Christopher Eccleston | [7, 18] | 10 | 10 | True |  |
| `metaqa_2hop_test_actor_to_movie_to_actor_000043` | Dick Haymes | [1, 7] | 6 | 6 | True |  |
| `metaqa_2hop_test_actor_to_movie_to_actor_000062` | Claudia Gerini | [1, 3] | 2 | 2 | True |  |
| `metaqa_2hop_test_actor_to_movie_to_actor_000065` | Sebastian Shaw | [1, 4] | 3 | 3 | True |  |
| `metaqa_2hop_test_actor_to_movie_to_actor_000067` | Gabriel Tigerman | [1, 4] | 3 | 3 | True |  |
| `metaqa_2hop_test_actor_to_movie_to_actor_000077` | Silvia Colloca | [1, 4] | 3 | 3 | True |  |
| `metaqa_2hop_test_actor_to_movie_to_actor_000080` | Pamela Flores | [1, 4] | 3 | 3 | True |  |
| `metaqa_2hop_test_actor_to_movie_to_actor_000100` | Harold Gould | [1, 4] | 3 | 3 | True |  |

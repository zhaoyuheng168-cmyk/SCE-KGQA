# MetaQA Coverage Smoke Failure Audit

- Input results: `/root/work/GansuTechFinance_KGQA_RELEASE_RUNTIME/deliverables/paper_submission_system_20260522_114215/experiments/public_datasets/metaqa/processed/coverage_smoke_49qtype_3each/metaqa_real_adapter_coverage_results.jsonl`
- Total smoke questions: **141**
- Failed questions audited: **40**
- Total extra answers: **1481**
- Total missing answers: **1**
- Failures with ambiguous subject-string roles: **3**
- Failures whose extra answers all have graph evidence: **40**

## Category Counts

- `extra_answers_have_valid_graph_paths`: 40
- `over_return_only`: 39
- `ambiguous_subject_string_roles`: 3
- `missing_gold_answers`: 1
- `mixed_mismatch`: 1

## Failures by Hop

| Hop | Failures |
|---:|---:|
| 1 | 16 |
| 2 | 4 |
| 3 | 20 |

## Failures by Qtype

| Qtype | Failures |
|---|---:|
| `movie_to_tags` | 3 |
| `movie_to_year` | 3 |
| `tag_to_movie` | 3 |
| `movie_to_writer_to_movie_to_year` | 3 |
| `movie_to_director` | 2 |
| `movie_to_writer` | 2 |
| `movie_to_actor_to_movie` | 2 |
| `movie_to_director_to_movie_to_actor` | 2 |
| `movie_to_director_to_movie_to_language` | 2 |
| `movie_to_director_to_movie_to_writer` | 2 |
| `movie_to_director_to_movie_to_year` | 2 |
| `movie_to_writer_to_movie_to_director` | 2 |
| `movie_to_writer_to_movie_to_genre` | 2 |
| `movie_to_actor` | 1 |
| `movie_to_genre` | 1 |
| `writer_to_movie` | 1 |
| `actor_to_movie_to_actor` | 1 |
| `movie_to_writer_to_movie` | 1 |
| `movie_to_actor_to_movie_to_director` | 1 |
| `movie_to_actor_to_movie_to_genre` | 1 |
| `movie_to_actor_to_movie_to_year` | 1 |
| `movie_to_director_to_movie_to_genre` | 1 |
| `movie_to_writer_to_movie_to_actor` | 1 |

## Representative Failures

| Hop | Qtype | Subject | Subject roles | Extra | Missing | Categories |
|---:|---|---|---|---|---|---|
| 1 | `movie_to_actor` | Time Without Pity | movie | Emma Thompson |  | extra_answers_have_valid_graph_paths ; over_return_only |
| 1 | `movie_to_director` | Make the Yuletide Gay | movie | Christopher Scott Cherot ; Fritz Lang ; Joseph Losey |  | extra_answers_have_valid_graph_paths ; over_return_only |
| 1 | `movie_to_director` | The Blind Sunflowers | movie | Eskil Vogt ; Vittorio De Sica |  | extra_answers_have_valid_graph_paths ; over_return_only |
| 1 | `movie_to_genre` | Road to Morocco | movie | Drama ; Romance ; Thriller |  | extra_answers_have_valid_graph_paths ; over_return_only |
| 1 | `movie_to_tags` | Miss Austen Regrets | movie | classic ; fritz lang ; peter lorre ; remake |  | extra_answers_have_valid_graph_paths ; over_return_only |
| 1 | `movie_to_tags` | Burden of Dreams | movie | akira kurosawa ; dreams ; kurosawa ; life |  | extra_answers_have_valid_graph_paths ; over_return_only |
| 1 | `movie_to_tags` | Holiday Inn | movie | bd-r ; cary grant ; comedy ; george cukor ; katharine hepburn |  | extra_answers_have_valid_graph_paths ; over_return_only |
| 1 | `movie_to_writer` | Molière | movie ; writer | Fritz Lang ; Grégoire Vigneron ; Laurent Tirard ; Thea von Harbou |  | ambiguous_subject_string_roles ; extra_answers_have_valid_graph_paths ; over_return_only |
| 1 | `movie_to_writer` | A Soldier's Story | movie | David Webb Peoples |  | extra_answers_have_valid_graph_paths ; over_return_only |
| 1 | `movie_to_year` | The Man Who Laughs | movie | 1928 ; 1931 ; 1951 ; 1972 ; 2005 |  | extra_answers_have_valid_graph_paths ; over_return_only |
| 1 | `movie_to_year` | Silent Night, Deadly Night | movie | 1987 ; 2012 |  | extra_answers_have_valid_graph_paths ; over_return_only |
| 1 | `movie_to_year` | Romance | genre ; movie | 1948 ; 1972 ; 1979 ; 1981 ; 1984 ; 1985 ; 1993 ; 2006 |  | ambiguous_subject_string_roles ; extra_answers_have_valid_graph_paths ; over_return_only |
| 1 | `tag_to_movie` | shahrukh khan | tag | 10 Items or Less ; 127 Hours ; 24 Hour Party People ; 30 Days of Night ; 300 ; 3000 Miles to Graceland ; 40 Days and 40 Nights ; 50/50 |  | extra_answers_have_valid_graph_paths ; over_return_only |
| 1 | `tag_to_movie` | cows | tag | A Short Film About Love |  | extra_answers_have_valid_graph_paths ; over_return_only |
| 1 | `tag_to_movie` | elisha cuthbert | tag | 10 Items or Less ; 127 Hours ; 24 Hour Party People ; 30 Days of Night ; 300 ; 3000 Miles to Graceland ; 40 Days and 40 Nights ; 50/50 |  | extra_answers_have_valid_graph_paths ; over_return_only |
| 1 | `writer_to_movie` | James Marsh | director ; writer | The Stupids |  | ambiguous_subject_string_roles ; extra_answers_have_valid_graph_paths ; over_return_only |
| 2 | `actor_to_movie_to_actor` | Angie Everhart | actor | Kevin Bacon |  | extra_answers_have_valid_graph_paths ; over_return_only |
| 2 | `movie_to_actor_to_movie` | Jack the Bear | movie | A Little Romance ; A Streetcar Named Desire ; A Walk on the Moon ; Aladdin ; An Unfinished Life ; Anaconda ; Angel Eyes ; Awakenings |  | extra_answers_have_valid_graph_paths ; over_return_only |
| 2 | `movie_to_actor_to_movie` | Avalanche | movie | All Is Bright ; Alpha Dog ; Clueless ; Dinner for Schmucks ; How Do You Know ; I Could Never Be Your Woman ; I Love You, Man ; Into the Wild |  | extra_answers_have_valid_graph_paths ; over_return_only |
| 2 | `movie_to_writer_to_movie` | Alila | movie | Heat ; Manhunter ; Miami Vice ; Public Enemies ; The Insider ; The Jericho Mile ; The Keep ; The Last of the Mohicans |  | extra_answers_have_valid_graph_paths ; over_return_only |

## Interpretation Guard

- A graph-supported extra answer is not automatically a framework error.
- It may indicate an ambiguous entity string, benchmark answer filtering, or a missing route constraint.
- This audit does not modify predictions, raw data, routes, or the unified core.

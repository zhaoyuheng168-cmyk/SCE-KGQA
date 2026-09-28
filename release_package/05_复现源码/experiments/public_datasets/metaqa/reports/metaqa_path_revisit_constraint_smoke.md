# MetaQA Start-Entity Revisit Constraint Smoke

## Purpose

Validate a domain-independent typed-path constraint that optionally excludes the
start entity when it is revisited at a configured intermediate path step.

## Tested route

`movie_to_actor_to_movie_to_director`

```text
movie
  -[starred_actors / out]->
actor
  -[starred_actors / in]->
movie
  -[directed_by / out]->
director
```

The question semantics refer to directors of *other* movies sharing actors with
the start movie. Therefore, revisiting the start movie at step 2 must be
excluded before continuing to step 3.

## Before

- Constraint: disabled.
- Exact match: **3/10**.
- Failure count: **7**.
- Failure pattern: all seven failures contained extra directors and no missing
  gold answers.
- Root cause: step 2 revisited the start movie, causing step 3 to return the
  start movie's own director.

## After

- Constraint: `exclude_start_at_steps=[2]`.
- Exact match: **10/10**.
- Failure count: **0**.

## Generality

The executor does not mention MetaQA, movies, actors, or directors in the
constraint implementation. A route or planner explicitly configures the
1-based path steps where start-entity revisits are semantically invalid.

The same mechanism can apply to:

- enterprise -> industry -> other enterprise -> product
- user -> group -> other user -> topic
- paper -> author -> other paper -> venue

The constraint is optional because some questions intentionally include the
start entity when traversing a cyclic path.


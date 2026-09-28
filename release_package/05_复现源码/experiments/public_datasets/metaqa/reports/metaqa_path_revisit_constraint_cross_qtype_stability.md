# MetaQA Start-Entity Revisit Constraint: Cross-Qtype Stability Smoke

## Goal

Test whether the optional start-entity revisit constraint improves multiple
3-hop typed paths with the same cyclic structure, rather than only one
director-target route.

## Constraint

`exclude_start_at_steps=[2]`

The tested route family has the structure:

```text
start movie -> actor -> movie -> target
```

At step 2, the path can revisit the start movie. Questions in this route family
ask about other movies sharing actors with the start movie, so the revisit must
be excluded before the final hop.

## Results

| Qtype | Constraint off | Constraint on | Change |
|---|---:|---:|---:|
| `movie_to_actor_to_movie_to_director` | 3/10 | 10/10 | +7 |
| `movie_to_actor_to_movie_to_genre` | 9/10 | 10/10 | +1 |
| **Combined** | **12/20** | **20/20** | **+8** |

## Failure Pattern

- All eight corrected failures were over-return errors.
- No corrected failure contained missing gold answers.
- The director route excluded 29 start-entity revisits at step 2.
- The genre route excluded 26 start-entity revisits at step 2.
- After enabling the constraint, extra answers and missing answers were both
  zero across the tested 20 questions.

For the genre route, the corrected question started from `Walk the Line`.
Without the constraint, the start movie's own genre `Music` was incorrectly
included. Excluding the step-2 revisit removed the unsupported extra answer.

## Interpretation

The result supports a structural, domain-independent typed-path constraint:

- It is not tied to a specific final target relation.
- It improves both director-target and genre-target routes.
- It does not reduce accuracy on questions already correct without the
  constraint.

This remains a bounded smoke result. Broader validation should later sample
additional cyclic qtypes before making a full benchmark claim.


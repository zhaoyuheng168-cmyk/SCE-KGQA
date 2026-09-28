# MetaQA Coverage Smoke Failure Root-Cause Analysis

## Scope

This report analyzes the 40 failures from the bounded 141-question coverage
smoke. It does not modify predictions, raw data, routes, or the unified core.

## Initial Failure Profile

- Questions executed: **141**
- Exact matches: **101**
- Failed questions: **40**
- Over-return-only failures: **39**
- Mixed mismatch failures: **1**
- Total extra answers: **1481**
- Total missing answers: **1**
- Every extra answer had a valid graph path.

## Primary Root Cause: Over-Permissive Subject Matching

The shared in-memory executor currently accepts subject candidates when:

```text
node == query
OR query contains node
OR node contains query
```

All **40/40** failed questions had:

- the correct exact subject present; and
- at least one additional fuzzy subject candidate.

Representative examples:

| Requested subject | Incorrect additional candidates |
|---|---|
| `Make the Yuletide Gay` | `G`, `M` |
| `Time Without Pity` | `Pi`, `Wit` |
| `The Blind Sunflowers` | `Blind`, `Sunflower` |
| `Romance` | `Roma`, `Roman`, `True Romance`, and others |
| `She` | 59 additional titles containing `She` |
| `shahrukh khan` | tags `r`, `s` |

These additional candidates generate valid graph paths but answer a different
entity-linking interpretation than the benchmark topic entity.

## Exact-Subject Counterfactual

The 40 failed questions were re-executed in a read-only counterfactual audit
using only the exact typed subject entity.

| Result | Count |
|---|---:|
| Failures fixed by exact typed subject matching | **38/40** |
| Remaining failures | **2/40** |

This implies a counterfactual bounded-smoke result of:

```text
139/141 exact matches
```

The exact-subject policy is appropriate for MetaQA because the topic entity is
explicitly marked with square brackets.

## Remaining Two Failures: Same-String Entity Collisions

### `Molière`

Question gold:

```text
Ariane Mnouchkine
```

The raw KB also contains:

```text
Molière|written_by|Grégoire Vigneron
Molière|written_by|Laurent Tirard
```

The same entity string refers to different movie records, but the raw
string-based KB provides no identifier that allows the executor to select only
the intended record.

### `The Man Who Laughs`

Question gold:

```text
2012
```

The raw KB also contains:

```text
The Man Who Laughs|release_year|1928
```

Again, the same movie-title string maps to multiple records while the question
provides no disambiguating identifier.

## Interpretation

The failures divide into two categories:

1. **Framework entity-linking policy issue, 38 questions**  
   MetaQA's explicitly bracketed subject should use exact typed matching rather
   than substring expansion.

2. **Irreducible string-level benchmark ambiguity, 2 questions**  
   The same subject string represents multiple graph records, while Gold selects
   only one record and the raw data provides no unique identifier.

## Formal-Experiment Blockers

Before formal MetaQA evaluation:

1. Promote entity matching into a configurable unified-core policy.
2. Configure the real MetaQA adapter to use exact typed subject matching.
3. Preserve fuzzy matching as an optional policy for real-world domains such as
   Gansu Finance.
4. Report same-string collision cases separately rather than hiding or
   gold-filtering them.
5. Re-run the bounded 49-qtype coverage smoke after the policy change.

## Research Value

This analysis identifies a second reusable framework boundary:

```text
Entity-linking policy must be configurable by domain.
```

Public benchmarks with explicitly marked topic entities benefit from strict
exact typed linking, while real industrial QA may require fuzzy candidate
generation followed by ranking and validation.


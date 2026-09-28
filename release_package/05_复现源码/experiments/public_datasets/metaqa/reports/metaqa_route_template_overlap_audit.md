# MetaQA Route-Template Overlap Audit

## Method

The bracketed topic entity in every question was replaced with
`TOPIC_ENTITY`. The resulting normalized natural-language templates were then
compared across the official train, dev, and test splits.

## Results

| Split | Questions | Unique normalized templates |
|---|---:|---:|
| Train | 329,282 | 521 |
| Dev | 39,138 | 518 |
| Test | 39,093 | 503 |

- Dev questions whose normalized template appears in Train: **39,138/39,138**.
- Test questions whose normalized template appears in Train: **39,093/39,093**.
- Dev unique templates appearing in Train: **518/518**.
- Test unique templates appearing in Train: **503/503**.
- Train templates associated with multiple qtypes: **0**.

## Interpretation

Official-split route prediction measures recognition of previously observed
question templates. It removes the Oracle-qtype input from execution, but it
does not test generalization to unseen natural-language templates.

The official predicted-route experiment should therefore be reported together
with a template-held-out experiment. In the held-out setting, templates are
partitioned within each qtype before training, and the classifier is evaluated
only on templates absent from its training data.

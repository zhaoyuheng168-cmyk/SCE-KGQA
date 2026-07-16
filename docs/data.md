# Data notes

## Frozen research-resource statistics

| Item | Count |
|---|---:|
| Graph nodes | 1707 |
| Graph relationships | 31018 |
| Business entity types | 11 |
| Relationship types | 20 |
| KG triple retrieval records | 22152 |
| Evidence chunks | 5612 |
| Merged retrieval corpus | 27764 |
| Formal evaluation questions | 1300 |

These counts describe the frozen research resources. They are not counts of
the files in this showcase.

## Public sample

`data/samples/graph_sample.json` contains 12 entities and 13 relations selected
from the frozen graph. Enterprise names and aliases are anonymized; entity
types, relation structure, regions, industries and qualification logic are
retained so the execution paths remain concrete. Full source URLs, raw
documents, long evidence text and personal contact information are omitted.

The sample includes core relations and expanded relations. In particular,
`servesEnterprise` in the sample is an expanded mapping from product target
groups to enterprise features. It must not be interpreted as proof that a
specific loan or subsidy event occurred.

## Excluded material

- Complete 1300-question test set and Gold answers
- Full graph export and retrieval corpora
- Raw website snapshots and PDF documents
- Full evidence text and embedding indexes
- Historical evaluation outputs

The public sample is for demonstration and code review, not for reproducing or
replacing the formal benchmark.

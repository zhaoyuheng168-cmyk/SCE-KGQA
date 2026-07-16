# Recruiter overview

## Three-minute summary

SCE-KGQA is a regional science and technology finance knowledge-service
project developed from March to July 2026. It organizes policies, financial
institutions, products, enterprises, regions, industries, qualifications and
service events in a domain knowledge graph, then answers questions through
Schema-constrained graph execution rather than unrestricted text generation.

## Engineering focus

- Normalizing aliases and ambiguous entity mentions
- Preserving relation direction in direct and reverse questions
- Constructing inspectable multihop paths
- Combining graph execution with business-rule filters
- Using evidence for traceability and weak-recall support
- Refusing questions outside the available knowledge boundary
- Freezing evaluation resources and auditing paper-to-result consistency

## Author contribution

The author led requirements analysis, Schema design, data processing,
environment deployment, system debugging, experiment design, result
verification and manuscript writing. GPT and Codex assisted with code
generation, debugging and engineering iteration.

## Scale and result

The research graph contains 1707 nodes and 31018 relationships. The retrieval
resources contain 22152 KG triple records and 5612 evidence chunks. On the
frozen 1300-question test set, the reported strict accuracy is 88.23% and the
task-aware success rate is 92.23%.

## What to inspect first

1. `src/sce_kgqa/engine.py` for the small executable workflow.
2. `data/samples/graph_sample.json` for the public graph subset.
3. `src/sce_kgqa/research_core/` for selected V8 implementation details.
4. `results/official/` for copied formal result summaries.
5. `tests/smoke_test.py` for behavior-level checks.

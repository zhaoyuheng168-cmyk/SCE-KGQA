# Unified Comparison Metrics

| Method | Rows | Strict Accuracy | Strict Macro F1 | Task-aware Success | Task-aware Macro F1 |
|---|---:|---:|---:|---:|---:|
| entity_linked_graphrag | 1300 | 19.23% | 21.22% | 21.23% | 11.36% |
| graph_only_kgqa | 1300 | 43.62% | 32.75% | 47.31% | 28.56% |
| hybrid_rag | 1300 | 52.62% | 56.30% | 55.08% | 52.63% |
| kg_context_rag | 1300 | 18.69% | 20.44% | 20.69% | 10.49% |
| langchain_rag | 1300 | 48.62% | 52.42% | 50.92% | 48.61% |
| llamaindex_rag | 1300 | 50.85% | 52.62% | 53.00% | 48.65% |
| llm_only | 1300 | 10.77% | 10.77% | 12.77% | 0.00% |
| naive_bm25_rag | 1300 | 51.31% | 52.86% | 53.46% | 49.04% |
| naive_vector_rag | 1300 | 48.77% | 52.63% | 51.23% | 48.91% |
| rule_based_kgqa | 1300 | 42.85% | 34.77% | 45.15% | 29.52% |
| sce_kgqa_full | 1300 | 88.23% | 79.05% | 92.23% | 85.15% |
| text_kg_rag | 1300 | 52.46% | 54.66% | 54.85% | 50.99% |

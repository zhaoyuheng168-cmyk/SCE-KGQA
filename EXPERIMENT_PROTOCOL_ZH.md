# SCE-KGQA 实验协议说明

## 1. 正式主结果

正式主结果使用 1300 题测试集。

主结果表：

`09_20260614_最终增补/final_experiment_package_20260613/tables/01_main_comparison_formal1300.csv`

关键指标包括：

- Strict Accuracy
- Strict Macro F1
- Task-aware Success
- Task-aware Macro F1

## 2. 主要基线

正式对比包括：

- LLM-only
- Graph-only KGQA
- Rule-based KGQA
- BM25-RAG
- Vector-RAG
- Text+KG RAG
- HybridRAG
- Official LightRAG
- LangChain-RAG
- LlamaIndex-RAG
- Entity-linked GraphRAG
- KG-Context RAG

## 3. 消融实验

主消融表：

`09_20260614_最终增补/final_experiment_package_20260613/tables/02_corrected_ablation_formal1300.csv`

目标题型贡献表：

`09_20260614_最终增补/final_experiment_package_20260613/tables/03_targeted_module_contribution_formal1300.csv`

可解释模块包括：

- Embedding enhancement
- Multihop reasoning
- Reverse relation
- Rule reasoning
- Open relation module
- Boundary/refusal gate

## 4. 补充实验

自然问法 100：

`09_20260614_最终增补/final_experiment_package_20260613/tables/04_natural_questions_100_ablation.csv`

V6 功能压力：

`09_20260614_最终增补/final_experiment_package_20260613/tables/05_functional_stress_v6_corrected.csv`

专项消融：

`09_20260614_最终增补/final_experiment_package_20260613/tables/06_specialty_ablations_summary.csv`

## 5. 迁移实验

MetaQA 迁移：

- `09_20260614_最终增补/final_experiment_package_20260613/tables/07_metaqa_transfer_summary.csv`
- `09_20260614_最终增补/final_experiment_package_20260613/tables/08_metaqa_transfer_ablation.csv`

GrailQA 只有只读审计，不作为成功迁移结果。

## 6. 显著性检验

显著性表：

`09_20260614_最终增补/final_experiment_package_20260613/source_tables/pairwise_significance.csv`

论文中可引用 SCE-KGQA 与主要基线之间的配对差异、置信区间和 McNemar exact p-value。

## 7. 口径注意

- 主对比 Full 为 `88.23%`，来自正式 1300 主对比表。
- 消融 Full 为 `88.31%`，来自修正消融口径。
- 两个数字来源不同，不能混用。
- `w/o boundary/refusal gate` 的 Macro F1 是非拒答类口径，必须说明。


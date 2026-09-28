# 无效和诊断结果声明

本文件用于防止公开包使用者误引用历史诊断结果。

## 1. 不可作为正式论文结果引用

以下内容不能作为正式结果：

1. `functional_stress_v4/v5`
   - 原因：问题生成和路由目标不够干净。

2. V6 combined summary 中的 `bm25_graph_text=0.00%`
   - 原因：脚本路径错误。
   - 替代：使用 `BM25-RAG fixed 58.00%`。

3. `without_kag_evidence smoke`
   - 原因：只有 3 个问题，是 smoke test。

4. `final_ablation_1300_kag_evidence_planner_20260613`
   - 原因：跑了 1800 行，不是正式 1300 口径。

5. GrailQA 成功迁移
   - 原因：只有 Stage-1 readonly audit，没有正式 benchmark 结果。

## 2. 正式排除依据

排除清单：

`09_20260614_最终增补/final_experiment_package_20260613/tables/09_invalid_or_diagnostic_results.csv`

## 3. 可引用替代结果

- 正式主对比：`01_main_comparison_formal1300.csv`
- 修正消融：`02_corrected_ablation_formal1300.csv`
- 目标题型贡献：`03_targeted_module_contribution_formal1300.csv`
- 自然问法 100：`04_natural_questions_100_ablation.csv`
- V6 corrected：`05_functional_stress_v6_corrected.csv`
- MetaQA：`07_metaqa_transfer_summary.csv` 和 `08_metaqa_transfer_ablation.csv`


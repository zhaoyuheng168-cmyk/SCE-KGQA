# SCE-KGQA 公开发布前审查报告

生成时间：2026-06-14  
审查对象：`SCE-KGQA_投稿代码复现包_20260614.tar.gz`  
审查方式：静态扫描压缩包文件名与文本内容；未运行评测；未调用外部接口；未修改原始包。

## 1. 总体结论

当前投稿复现包具备公开基础。未发现真实 `.env`、`kag_config.yaml`、私钥文件、后台 PID、后台日志或明确 API key 文件名泄露。扫描中命中的 `.env`、`kag_config.yaml` 多为代码或说明文档里的配置路径引用，不是实际密钥文件。

公开前仍需补充公开版说明，重点解释数据来源、许可边界、正式/废弃结果区分、baseline 公平性和复现步骤。

## 2. 扫描范围

- 文件总数：7223
- 目录总数：194
- 文本扫描文件数：7131
- 文本扫描体量：约 80 MB
- 精扫后文件名风险数：0
- 精扫后内容命中数：29

扫描记录：

- `codex_reports/public_release_scan_20260614.json`
- `codex_reports/public_release_scan_refined_20260614.json`

## 3. 敏感信息检查

| 检查项 | 结论 | 说明 |
|---|---|---|
| API key | 未发现真实 key | 没有发现 `sk-...` 形式真实密钥；`api_key` 命中主要来自配置说明或代码读取逻辑 |
| `.env` | 未发现真实 `.env` 文件 | 命中来自代码和 README 中的说明；`.env.example` 可保留 |
| `kag_config.yaml` | 未发现真实配置文件 | 命中来自排除说明或代码读取逻辑 |
| 私钥文件 | 未发现 | 未发现 `id_rsa`、`id_ed25519` 文件 |
| 服务器 IP/端口 | 未发现真实服务器地址 | 精扫中 `24944` 命中为 LightRAG token usage 的 `total_tokens` 数字，不是端口 |
| 后台日志/PID | 未发现真实后台文件名 | 原始包已排除 `*_background.log`、`.pid`、`nohup.out` |

## 4. 可公开内容

建议公开：

- SCE-KGQA 源码快照。
- Schema 与业务规则。
- 结构化图谱节点/边快照。
- evidence corpus、entity lexicon、merged RAG corpus。
- 1300 正式测试集与 expanded gold。
- 自然问法 100、V6 功能压力测试、MetaQA 迁移结果。
- 正式对比、修正消融、显著性检验和专项消融表。
- 环境配置样例、复现脚本、结果说明、SHA256。

## 5. 需要明确说明的公开边界

1. 原始网页/HTML/PDF 快照如果公开，必须说明来源为公开网页，研究用途，版权归原发布方。
2. 若期刊或平台不适合发布全文网页快照，建议只公开 URL、抽取事实、证据片段和构建脚本。
3. 复现包中不能包含 API key、服务器密码、私钥、真实 `.env` 或真实 `kag_config.yaml`。
4. 废弃实验不能作为正式结果引用。
5. baseline 必须说明同一测试集、同一 gold、同一 corpus 范围与参数。

## 6. 必须排除或隔离的内容

当前包未发现真实敏感文件。公开重打包仍执行以下排除规则：

- `.git/`
- `.env`，但保留 `.env.example`
- `kag_config.yaml`
- `*.pid`
- `*_background.log`
- `nohup.out`
- 私钥文件：`id_rsa`、`id_ed25519`
- 临时缓存目录：`__pycache__/`

## 7. 正式结果和废弃结果边界

可正式引用：

- `01_main_comparison_formal1300.csv`
- `02_corrected_ablation_formal1300.csv`
- `03_targeted_module_contribution_formal1300.csv`
- `04_natural_questions_100_ablation.csv`
- `05_functional_stress_v6_corrected.csv`
- `07_metaqa_transfer_summary.csv`
- `08_metaqa_transfer_ablation.csv`
- `pairwise_significance.csv`

不能正式引用：

- V4/V5 功能压力测试。
- 错误 `bm25_graph_text=0.00%`。
- 3 题 KAG smoke。
- `final_ablation_1300_kag_evidence_planner_20260613` 诊断结果。
- GrailQA 成功迁移说法。

证据路径：`09_20260614_最终增补/final_experiment_package_20260613/tables/09_invalid_or_diagnostic_results.csv`

## 8. 公开发布建议

可以发布公开版包，但要使用新包名和公开说明文档：

- `SCE-KGQA_public_release_20260614.tar.gz`
- `SCE-KGQA_public_release_20260614.tar.gz.sha256`
- `PUBLIC_RELEASE_README_ZH.md`
- `DATASET_CARD_ZH.md`
- `EXPERIMENT_PROTOCOL_ZH.md`
- `BASELINE_FAIRNESS_CHECKLIST_ZH.md`
- `INVALID_RESULTS_NOTICE_ZH.md`
- `REPRODUCIBILITY_CHECKLIST_ZH.md`

该公开包适合作为论文补充材料或开源仓库初始发布包。


# SCE-KGQA 数据集卡片

## 1. 数据集名称

SCE-KGQA Gansu Tech-Finance KGQA Dataset。

## 2. 数据集目标

支撑区域科技金融知识服务场景下的知识图谱问答研究，覆盖企业、金融产品、金融机构、政策、区域、产业、资格/信用特征、贷款事件、补贴事件和证据文本。

## 3. 数据来源

数据来自公开渠道，包括政府公开政策、科技/工信/金融相关公开页面、金融机构公开产品与服务页面、企业和事件类公开报道，以及项目构建的结构化知识图谱快照。

重要说明：公开网页和原始页面内容的权利仍属于相应权利人，学术研究用途不能自动提供全文转载许可。
本地候选附件排除原始网页全文；加工证据和图谱中的第三方表达也需要确认授权。
许可范围与来源状态见 `DATA_LICENSE_ZH.md`、`SOURCE_RIGHTS_MANIFEST.csv`、`RELEASE_STATUS_ZH.md`。

## 4. 数据内容

以下路径均位于仓库根目录的 `release_package/` 下：

- `04_数据与知识资源/benchmark/gtf_kgqa_1300_formal.csv`
- `04_数据与知识资源/benchmark/gtf_kgqa_1300_formal_expanded_gold.csv`
- `04_数据与知识资源/corpus/kg_triples_corpus.jsonl`
- `04_数据与知识资源/corpus/evidence_corpus.jsonl`
- `04_数据与知识资源/corpus/merged_rag_corpus.jsonl`
- `04_数据与知识资源/corpus/entity_lexicon.jsonl`
- `04_数据与知识资源/runtime_data/`
- `04_数据与知识资源/unstructured_pipeline_snapshot/`
- `04_数据与知识资源/structured_build_snapshot/`

## 5. 规模

根据 `04_数据与知识资源/corpus/corpus_v1_report.md`：

- KG triples：22152
- Evidence chunks：5612
- Merged corpus total：27764

根据 `06_环境与配置/REPRODUCE_METRICS.md` 的 Neo4j 恢复说明：

- Nodes：1707
- Relationships：31018

## 6. 主要关系

语料报告中的高频关系包括：

- `targetsEnterprise`
- `servesEnterprise`
- `hasFeature`
- `locatedIn`
- `benefitsEnterprise`
- `belongsToIndustry`
- `connects`
- `supports`
- `loanToEnterprise`
- `issues`
- `providesProduct`
- `grantsSubsidy`
- `issuesLoan`
- `matchesFinancing`

## 7. 测试集

正式主测试集：

- `gtf_kgqa_1300_formal.csv`
- `gtf_kgqa_1300_formal_expanded_gold.csv`

补充测试：

- 自然问法 100 题。
- V6 功能压力 100 题。
- MetaQA 迁移实验结果。

## 8. 数据泄露控制

`corpus_v1_report.md` 声明 corpus 只由冻结运行时 KG 和 evidence files 构建，不读取测试 gold 字段。论文中仍应说明测试集生成、审核和 gold 扩展流程。

## 9. 适用任务

- 垂直领域 KGQA。
- Schema-constrained KGQA。
- Evidence-grounded QA。
- Text+KG RAG 和 GraphRAG baseline 对比。
- 多跳问答、反向关系问答、规则推理和拒答控制评测。

## 10. 不适用场景

- 不适合直接作为通用开放域百科问答数据集。
- 不适合把原始网页全文当作可自由再授权内容使用。
- 不适合作为金融投资建议或政策法律解释依据。


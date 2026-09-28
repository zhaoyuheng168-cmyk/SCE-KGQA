# 甘肃省科技金融知识图谱问答系统

SCE-KGQA — 完整研究复现交付版，版本 `2026.09.28`。

本项目围绕领域 Schema、Neo4j 图查询、显式多跳、规则推理、实体归一、
证据检索和拒答边界实现科技金融知识图谱问答。

## 完整资产入口

| 资产 | 位置 | 规模 |
|---|---|---:|
| 正式问题与原始 Gold | `release_package/04_数据与知识资源/benchmark/gtf_kgqa_1300_formal.csv` | 1300 题 |
| 正式评分 expanded Gold | `release_package/04_数据与知识资源/benchmark/gtf_kgqa_1300_formal_expanded_gold.csv` | 1300 题 |
| 全量冻结图谱 | `release_package/04_数据与知识资源/runtime_data/neo4j_export/` | 1707 节点、31018 关系 |
| 图谱语料 | `release_package/04_数据与知识资源/corpus/kg_triples_corpus.jsonl` | 22152 条 |
| 加工后的完整证据语料 | `release_package/04_数据与知识资源/corpus/evidence_corpus.jsonl` | 5612 条 |
| 合并检索语料 | `release_package/04_数据与知识资源/corpus/merged_rag_corpus.jsonl` | 27764 条 |
| 完整研究源码、适配器、评分器 | `release_package/05_复现源码/` | 冻结研究实现 |
| 正式逐题输出 | `release_package/03_正式结果/` | 对比与消融 |
| 正式汇总表 | `release_package/09_20260614_最终增补/final_experiment_package_20260613/tables/` | 比较、消融、补充实验 |
| KQA Pro 迁移脚本与结果 | `release_package/10_kqapro_transfer/` | 冻结迁移实验 |

正式主结果使用 **expanded Gold** 评分。原始 Gold 和 expanded Gold 同时保留，不能互相替换。
图谱边数和检索三元组条数属于不同统计口径。

## 不调用模型即可检查数据并复算正式结果

完整图谱、加工证据、向量索引、原实验逐题输出和迁移数据保留全量，通过 [Release 附件](https://github.com/zhaoyuheng168-cmyk/SCE-KGQA/releases/tag/v2026.09.28) 交付。
使用以下命令自动下载、核对 SHA256 并恢复到仓库（也支持 --archive 指定本地 ZIP）：

```bash
python scripts/fetch_assets.py
```

完成附件恢复后运行：

```bash
python tools/validate_release.py
pip install -r requirements-core.lock
python scripts/recompute_metrics.py --method sce_kgqa_full
```

预期正式主结果：1300 题，Strict accuracy `88.230769%`，
Task-aware success `92.230769%`。消融 Full System `88.31%` 是另一份冻结输出，
不能拿来覆盖主比较结果。历史说明和废弃结果见 `INVALID_RESULTS_NOTICE_ZH.md`。

## 从干净环境启动实际问答后端

需要 Docker、Python 3.10 或更新版本。生成式路由如需调用在线模型，使用自己的 API Key。

```bash
cp .env.example .env
# 编辑 .env，为本地 Neo4j 设置自己的密码。
docker compose up -d neo4j
pip install -r requirements-core.lock
python scripts/restore_graph.py
python scripts/prepare_runtime.py
python scripts/run_qa.py --check
python scripts/run_qa.py "甘肃银行提供哪些科技金融产品？"
```

Windows PowerShell 使用 `Copy-Item .env.example .env`。
若需要完整向量辅助功能，再执行：

```bash
pip install -r requirements-reproduction.lock
# 历史 BGE 已包含在完整附件中；无需再次下载。
```

完整附件包含与历史服务器一致的 BGE 模型，模型清单记录版本及文件哈希。
本包没有自研大模型权重；历史生成模型通过 API 调用，BGE 为第三方嵌入模型。
见 `models/MODEL_MANIFEST.json` 和 `docs/ENVIRONMENT_ZH.md`。

## 前端

```bash
pip install -r requirements-frontend.txt
streamlit run app/frontend_streamlit/app.py
```

前端读取正式 1300 题、冻结结果与图谱，不再展示旧 1200 题 headline。
实际问答按钮调用公开源码，而不是读取 Gold 返回答案。

## 发布与许可

项目自有代码沿用 MIT。项目自有问题标注、Gold、研究文档与结果表使用 CC BY 4.0，
该授权仅涵盖项目有权许可的部分。第三方原始文献、网页、模型与外部数据继续适用原条款。
完整证据和图谱中的来源文本不因加入本项目而自动变成 MIT 或 CC BY 4.0。
见 `DATA_LICENSE_ZH.md`、`THIRD_PARTY_NOTICES.md`、`SOURCE_RIGHTS_MANIFEST.csv`。

发布布局为 **代码和 Gold 仓库 + 全量数据/结果 ZIP 附件**。原始网页全文、
服务器镜像、历史凭据、缓存和数据库数据卷不进入公开附件。
所有保留资产及排除项均有清单；具体发布状态见 `RELEASE_STATUS_ZH.md`。
项目引用见 `CITATION.cff`。

## 原实验入口与迁移范围

迁移只保留当时完成的程度。完整源码与历史结果已交付，部署后的执行入口、实际验收边界见 `docs/REPRODUCTION_SCOPE_ZH.md` 和 `VALIDATION_REPORT_ZH.md`。

```bash
python scripts/run_experiments.py --suite main
# 查看计划后加 --execute 运行；其余 suite: ablation / natural / stress / kqapro-frozen
```

## 迁移模型

BGE 历史模型已包含于附件。KoPL 原模型使用固定官方版本，执行以下命令下载并核对历史权重 SHA256：

```bash
python scripts/download_models.py --model kopl
```

公开包保留 KQA Pro 原数据、冻结候选、逐题预测和原迁移脚本，仅复现当时完成的迁移范围。

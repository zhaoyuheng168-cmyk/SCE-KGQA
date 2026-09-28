# SCE-KGQA 复现检查清单

## 1. 环境准备

优先阅读：

- `06_环境与配置/README_REPRODUCIBILITY.md`
- `06_环境与配置/REPRODUCE_METRICS.md`
- `06_环境与配置/environment.yml`
- `06_环境与配置/requirements.txt`

## 2. 服务依赖

主要依赖：

- Python / conda
- Neo4j
- 项目环境变量
- 可选的大模型 API 配置

公开包不提供真实 API key。需要调用外部模型时，使用者应自行配置。

## 3. 图谱恢复

根据 `REPRODUCE_METRICS.md`：

- 使用 `runtime_data/neo4j_export/` 中的 JSONL。
- 启动本地 Neo4j。
- 运行恢复脚本。
- 期望恢复规模：nodes 1707，relationships 31018。

## 4. 指标复现

建议先复现离线指标表，再尝试运行完整问答：

1. 检查正式结果表。
2. 检查 paired significance。
3. 检查 corrected ablation。
4. 检查 MetaQA transfer。
5. 如环境完整，再运行 QA demo 或 batch evaluation。

## 5. 不应执行的操作

- 不要使用包内废弃实验作为正式结论。
- 不要把 `.env.example` 当真实密钥。
- 不要把 `kag_config.yaml` 示例说明当真实配置。
- 不要删除或覆盖原始结果。
- 不要混用主对比口径和消融口径。

## 6. 校验

公开包应附：

- `SCE-KGQA_public_release_20260614.tar.gz.sha256`
- `SHA256SUMS.txt`

下载后先校验哈希，再复现实验。


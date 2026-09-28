# Baseline 公平性检查清单

论文和复现时，每个 baseline 至少应说明以下内容。

## 1. 通用检查项

| 检查项 | 要求 |
|---|---|
| 测试集 | 使用同一 1300 正式测试集 |
| Gold | 使用同一 gold / expanded gold 口径 |
| Corpus | 使用冻结的 KG/evidence/merged corpus |
| 输入 | 不得读取 gold answer 字段 |
| 私有模块 | baseline 不得调用 SCE-KGQA 的专有推理模块 |
| 参数 | 公开 top-k、chunk top-k、embedding 模型、LLM 模型 |
| 失败处理 | 公开 timeout、空答案和异常处理 |
| 指标 | 使用同一 strict 和 task-aware 指标脚本 |

## 2. 需要重点说明的 baseline

- BM25-RAG：应使用 fixed 有效版本，不使用旧 `bm25_graph_text=0.00%` 错误结果。
- Vector-RAG：说明 embedding 模型、index 和 top-k。
- Text+KG RAG：说明文本与 KG corpus 的组合方式。
- HybridRAG：说明融合策略和是否调用 LLM。
- LightRAG：说明官方框架配置、缓存、模型、query mode。
- LangChain / LlamaIndex：说明 adapter 是否只使用公开 corpus。
- Graph-only KGQA：说明不使用证据 fallback、LLM rewriting 或 SCE 专有模块。
- LLM-only：说明不给外部知识或 gold。

## 3. 论文中建议呈现

建议在附录增加一张 baseline protocol 表，字段包括：

- baseline name
- input corpus
- retrieval method
- graph access
- LLM model
- top-k
- uses SCE-only module
- uses gold
- timeout policy
- result path

## 4. 已知风险

历史 V6 中 `bm25_graph_text=0.00%` 是无效结果，原因是脚本路径错误；正式公开和论文只能使用 `BM25-RAG fixed 58.00%` 或正式 1300 主对比表中的 BM25-RAG。


# Embedding 模块说明

本文档用于说明本交付包中的 embedding 增强模块到底做了什么、依赖哪些文件，以及论文中应如何准确表述。

## 1. 结论

当前交付包已经补入真实向量 embedding 子系统，包含：

- 本地中文向量模型：`runtime_data/models/bge-small-zh-v1.5`
- embedding 代码：`app/retrieval_only/embedding/`
- FAISS 索引：
  - `app/retrieval_only/embedding_indexes/entity_names/faiss.index`
  - `app/retrieval_only/embedding_indexes/relation_schema/faiss.index`
  - `app/retrieval_only/embedding_indexes/evidence_chunks/faiss.index`
- embedding 实验配置：`configs/experiments/*.env`
- V8 问答入口中的 embedding 辅助接入：`app/retrieval_only/scripts/answer_hybrid_v8_graph_kag_fallback.py`

因此，这不是只有模板词、字符重叠或 SequenceMatcher 的鲁棒规则模块；它确实包含 `sentence-transformers`、`bge-small-zh-v1.5` 和 FAISS 向量检索。

但论文表述要严谨：embedding 在本系统中不是独立生成最终答案的模块，而是图谱问答主链路的辅助增强层。最终答案仍然必须经过图谱路径、schema 类型、规则推理、多跳规划、KAG 证据或拒答边界约束。

## 2. 工作原理

### 2.1 离线建库

离线阶段把三类文本转成向量并写入 FAISS：

1. 实体名称索引
   - 来源：图谱实体名、别名、规范名。
   - 目标：提高错别字、简称、后缀省略、实体顺序扰动、近名实体等情况下的实体落地能力。
   - 输出：`embedding_indexes/entity_names/faiss.index` 和 `metadata.jsonl`。

2. 关系语义索引
   - 来源：关系 schema、自然语言关系描述、目标类型约束。
   - 目标：把用户自由问法映射到系统已有的关系链路，例如“谁发的”“属于哪个产品”“面向哪些企业/地区/行业”等。
   - 输出：`embedding_indexes/relation_schema/faiss.index` 和 `metadata.jsonl`。

3. 证据片段索引
   - 来源：结构化证据卡、KAG 证据文档、事实片段。
   - 目标：用于 Text-RAG baseline、evidence assist 或消融实验。
   - 输出：`embedding_indexes/evidence_chunks/faiss.index` 和 `metadata.jsonl`。

向量模型为包内 `runtime_data/models/bge-small-zh-v1.5`，默认后端为 `sentence_transformers`。索引检索由 `faiss-cpu` 完成。

### 2.2 在线问答

在线阶段不会让 embedding 直接回答问题，而是按以下方式辅助 V8：

1. 用户问题先被 BGE 模型编码成向量。
2. FAISS 在实体、关系或证据索引中召回候选项。
3. V8 根据候选实体、候选关系和候选类型重新判断可执行链路。
4. 系统只执行已有图谱 schema 允许的 Cypher 或已有规则推理路径。
5. 返回答案前仍经过图谱结果、类型边界、多跳规划、KAG 证据或拒答策略约束。

也就是说，embedding 负责“召回候选、辅助路由、关系语义匹配、答案重排”，不负责“凭向量相似度直接编答案”。

## 3. 主要开关

推荐完整系统配置：

```bash
source configs/experiments/ours_embedding_full.env
```

核心开关含义：

- `GTF_ENABLE_EMBEDDING=1`：总开关。
- `GTF_ENABLE_EMBEDDING_ENTITY_CANDIDATES=1`：开启实体向量候选召回。
- `GTF_ENABLE_ENTITY_EMBEDDING_GROUNDING=1`：兼容旧名称，开启实体 grounding。
- `GTF_ENABLE_EMBEDDING_RELATION_FALLBACK=1`：当常规路由失败或出现目标类型冲突时，用关系向量召回辅助重试。
- `GTF_ENABLE_EMBEDDING_ANSWER_RERANK=1`：对已有图谱答案做辅助重排，不生成新答案。
- `GTF_ENABLE_EMBEDDING_EVIDENCE=0`：主系统默认关闭证据向量直接辅助；只建议在 Text-RAG baseline 或 evidence 消融实验中开启。

## 4. 论文中推荐写法

推荐写：

> 本文设计了面向领域知识图谱问答的向量增强鲁棒语义路由机制。该机制基于中文句向量模型与 FAISS 索引，对实体名称、关系 schema 与证据片段进行向量化召回，并将召回结果作为图谱问答主链路的实体归一化、关系语义匹配、路由仲裁和答案重排信号。系统最终答案仍由图谱路径、schema 类型约束、规则推理、多跳规划与证据边界共同约束。

不建议写：

> 系统完全依靠 FAISS/BGE 直接完成答案生成。

也不建议只写：

> 系统只是基于字符相似度做实体归一化。

准确定位应是：向量 embedding 辅助的知识图谱问答增强层。

## 5. 对已经跑过结果的归因

如果评测结果是在加载 `configs/experiments/ours_embedding_full.env` 后运行，且日志或结果字段中出现 `embedding_relation_grounding`、`embedding_route_arbitration`、`embedding_*_candidates` 等信息，则可以归因为使用了真实 embedding 辅助链路。

历史版本曾出现过 `embedding_robust_*` 路由名。该类 legacy 启发式路由已经从当前投稿主路径隔离，不再作为 embedding 模块的一部分。当前版本中，论文所称 embedding 仅指 `app/retrieval_only/embedding/`、`embedding_indexes/`、`sentence-transformers`/BGE 模型和 FAISS 索引组成的真实向量召回、关系 grounding 与答案重排链路。

## 6. 消融实验建议

推荐把当前完整系统作为主系统，然后做以下消融：

- Full：`ours_embedding_full.env`
- No relation fallback：关闭 `GTF_ENABLE_EMBEDDING_RELATION_FALLBACK`
- No entity candidates：关闭 `GTF_ENABLE_EMBEDDING_ENTITY_CANDIDATES` 和 `GTF_ENABLE_ENTITY_EMBEDDING_GROUNDING`
- No answer rerank：关闭 `GTF_ENABLE_EMBEDDING_ANSWER_RERANK`
- Text-RAG baseline：`baseline_text_rag_embedding.env`

这样能证明 embedding 不是额外外挂结果，而是作为主系统中的可控增强组件参与整体性能。

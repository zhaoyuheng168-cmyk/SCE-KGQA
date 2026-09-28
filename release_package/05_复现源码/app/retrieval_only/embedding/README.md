# Stage EMB：Embedding 实验支线说明

本目录为甘肃科技金融 KGQA runtime 新增一条 embedding 语义召回实验支线。它是旁路实验能力，不替代当前 Graph-first V8/V7 主系统。

## 核心原则

Embedding 主线只负责提升用户问题鲁棒性和多结果展示鲁棒性：前置实体候选、关系候选后备、`graph_answers` 辅助排序。结构化判断仍由图谱、Type Gate、规则推理、多跳 planner、Safety Gate 和 KAG evidence 约束完成。

`evidence assist` 不进入推荐主流程，只保留为 optional / ablation / debug 实验能力，避免和既有 KAG evidence 重复造成主流程臃肿。

本阶段不修改 V8/V7 默认问答行为。

## 新增模块说明

- `embedding_config.py`：集中读取 embedding 相关环境变量。它没有副作用，不会加载模型、读取索引、连接 Neo4j 或改变 V8/V7 行为。
- `embedding_backend.py`：封装 embedding 后端、向量归一化、FAISS 读写和检索。核心原理是先把向量归一化，再用内积近似余弦相似度。
- `build_evidence_embedding_index.py`：扫描 evidence 文档、KAG evidence cards、structured evidence docs，切分文本 chunk，生成 evidence 向量索引。构建时会排除 `reports/`、`manifest`、`report`、`summary` 等运行报告或清单文件，避免把索引过程的日志当成证据；同时会对所有来源的 chunk 做全局精确文本 hash 去重，不管重复文本来自同一文件夹还是不同文件夹，都只保留一份。
- `build_entity_embedding_index.py`：只读连接 Neo4j，读取核心实体 `name` 和 `labels`，生成实体候选向量索引。不写 Neo4j，不创建 Neo4j Vector Index。
- `embedding_retriever.py`：提供统一 evidence/entity 检索接口。索引或模型不可用时返回空列表并输出 warning，避免影响主系统。
- `entity_embedding_grounder.py`：实体语义召回测试模块，只输出候选实体，不生成最终答案，也不直接改写 V8 subject。
- `hybrid_embedding_evidence.py`：optional / ablation only 的 evidence support 接口，不推荐接入主流程。它只用于论文消融、调试和展示，不替代 KAG evidence。
- `embedding_pipeline_proposal.py`：定义未来 KGQA 管线中的 embedding 辅助边界：实体候选前置、关系候选后备、答案排序后置。它只输出候选，不确认实体、关系或答案。
- `embedding_assist_wrapper.py`：独立实验 wrapper，串联实体候选、关系选择和严格 evidence 检索，只返回 assist/evidence candidates，不生成最终答案，不替代 `graph_answers`。该模块仅用于实验，不推荐接入主流程。
- `embedding_assist_wrapper_smoke_runner.py`：小样本 smoke runner，批量运行 wrapper，输出 JSONL 和 Markdown 报告。它只评估 assist/evidence candidates，不评估最终答案；属于 evidence assist 实验工具。
- `graph_answer_reranker.py`：对 KG/V8 已返回的 `graph_answers` 做 embedding 辅助排序。它不新增、不删除、不验证答案，只增加 `embedding_score` 和辅助展示顺序。
- `graph_answer_rerank_smoke_runner.py`：小样本 rerank runner，模拟多结果 `graph_answers`，输出 JSONL 和 Markdown 排序报告。
- `embedding_robustness_smoke_runner.py`：用户问法鲁棒性小样本 runner，覆盖简称/别名、口语关系、多答案排序和边界问题。
- `text_rag_embedding_baseline.py`：普通 Text-RAG embedding 对比基线。它只根据 evidence chunks 回答，不调用 Neo4j、V8、V7、Type Gate、规则推理、泛关系 fallback 或多跳 planner。

## 新增实验配置说明

- `configs/experiments/baseline_text_rag_embedding.env`：开启纯 Text-RAG baseline，只启用 evidence embedding，不启用 entity grounding。
- `configs/experiments/ours_with_embedding_evidence.env`：保留当前 V8/V7/KAG/泛关系/多跳能力，同时只开启 embedding evidence support。该配置仅用于 optional / ablation 实验，不作为主流程推荐配置。
- `configs/experiments/ours_with_entity_embedding.env`：保留当前主系统能力，同时只开启 entity embedding grounding。
- `configs/experiments/ours_embedding_full.env`：开启主线推荐的 embedding 能力基础开关和 entity embedding grounding；不默认开启 evidence assist。

这些配置文件使用 `export KEY=value`，确保 `source` 后变量能传给 Python 子进程。

## 环境变量

所有 embedding 功能默认关闭：

```bash
GTF_ENABLE_EMBEDDING=0
GTF_ENABLE_EMBEDDING_EVIDENCE=0  # 主流程保持关闭；仅 evidence 消融实验开启
GTF_ENABLE_ENTITY_EMBEDDING_GROUNDING=0
GTF_ENABLE_EMBEDDING_ENTITY_CANDIDATES=0
GTF_ENABLE_EMBEDDING_RELATION_FALLBACK=0
GTF_ENABLE_EMBEDDING_ANSWER_RERANK=0
```

主要参数：

```bash
GTF_EMBEDDING_BACKEND=sentence_transformers
GTF_EMBEDDING_MODEL_NAME=
GTF_EMBEDDING_EVIDENCE_TOP_K=5
GTF_EMBEDDING_EVIDENCE_MIN_SCORE=0.65
GTF_ENTITY_EMBEDDING_TOP_K=10
GTF_ENTITY_EMBEDDING_MIN_SCORE=0.70
GTF_EVIDENCE_EMBEDDING_INDEX_DIR=app/retrieval_only/embedding_indexes/evidence_chunks
GTF_ENTITY_EMBEDDING_INDEX_DIR=app/retrieval_only/embedding_indexes/entity_names
```

主线推荐开关含义：

- `GTF_ENABLE_EMBEDDING_ENTITY_CANDIDATES`：开启前置实体候选。
- `GTF_ENABLE_EMBEDDING_RELATION_FALLBACK`：开启原关系链路失败后的关系候选后备。
- `GTF_ENABLE_EMBEDDING_ANSWER_RERANK`：开启 `graph_answers` 后置辅助排序。
- `GTF_ENABLE_EMBEDDING_EVIDENCE`：仅用于 evidence assist / Text-RAG baseline / 消融实验，主流程保持关闭。

`GTF_ENABLE_ENTITY_EMBEDDING_GROUNDING` 是早期兼容开关；未来主线接入应优先看 `GTF_ENABLE_EMBEDDING_ENTITY_CANDIDATES`。

当前 runtime 可能没有安装 `faiss` 或 `sentence_transformers`。这种情况下，构建脚本会写出清晰的 `build_report.md` 并退出，不修改原始 evidence、Neo4j、V8 或 V7。

## 构建 Evidence Index

```bash
python app/retrieval_only/embedding/build_evidence_embedding_index.py
```

依赖和模型可用时，期望输出：

```text
app/retrieval_only/embedding_indexes/evidence_chunks/faiss.index
app/retrieval_only/embedding_indexes/evidence_chunks/metadata.jsonl
app/retrieval_only/embedding_indexes/evidence_chunks/build_report.md
```

## 构建 Entity Index

```bash
python app/retrieval_only/embedding/build_entity_embedding_index.py
```

该脚本只读取 Neo4j 实体名称和标签，不写入 embedding 属性，不创建 Neo4j vector index。

依赖和模型可用时，期望输出：

```text
app/retrieval_only/embedding_indexes/entity_names/faiss.index
app/retrieval_only/embedding_indexes/entity_names/metadata.jsonl
app/retrieval_only/embedding_indexes/entity_names/build_report.md
```

## 检索 Smoke

```bash
source configs/experiments/baseline_text_rag_embedding.env
python app/retrieval_only/embedding/embedding_retriever.py \
  --mode evidence \
  --query "科技创新再贷款支持哪些企业" \
  --top-k 5

python app/retrieval_only/embedding/embedding_retriever.py \
  --mode evidence \
  --query "兰州银行有哪些科技金融产品" \
  --entity-filter "兰州银行" \
  --source-relation-filter providesProduct \
  --strict-entity-filter \
  --min-score 0.60 \
  --top-k 5

source configs/experiments/ours_with_entity_embedding.env
python app/retrieval_only/embedding/embedding_retriever.py \
  --mode entity \
  --query "科创再贷款" \
  --top-k 10

source configs/experiments/ours_embedding_full.env
python app/retrieval_only/embedding/embedding_assist_wrapper.py \
  --query "兰州银行有哪些科技金融产品" \
  --entity "兰州银行" \
  --relation providesProduct \
  --graph-answer "政采e贷" \
  --evidence-min-score 0.60
```

如果索引或模型不可用，检索会返回空列表并输出 warning。这是刻意设计的安全失败行为。

`--entity-filter` 会先多取候选，再优先返回结构化实体锚点中包含指定实体名的 evidence。实体锚点包括 `实体名称：...`、`事实1：...`、`事实三元组：...`、`Structured Fact`、metadata `entity_mentions`、文件名和路径。这个实体名应来自 KG 中已经出现过的实体或实体别名，用于减少纯语义检索把相似金融语境错召回到其他主体上的情况。

`--source-relation-filter` 用于指定 KG 关系名，例如 `providesProduct`、`servesEnterprise`、`supports`。检索器会优先匹配 evidence 正文中的 `包含关系：xxx`，并兼容文件名、路径或文本里的关系名。

默认情况下，如果过滤结果不足，检索器会用原始语义结果补齐 top-k。加上 `--strict-entity-filter` 后，只返回同时满足实体过滤和关系过滤的 chunk，不再补齐无关 evidence。

`--candidate-multiplier` 控制过滤前多取多少候选，默认是 500。严格实体/关系过滤属于“先语义粗召回、再 KG 约束精过滤”，候选池需要比普通 embedding 检索更大。加了实体和关系硬约束后，可以把 `--min-score` 临时降到 `0.60` 左右，避免短结构化事实因为语义分数略低被提前过滤掉。

`embedding_assist_wrapper.py` 有两种模式。无论哪种模式，它的输出都只是辅助候选，不是最终答案；最终答案实体枚举仍应来自图谱查询、V8/V7 受控路径或既有 answer composer。

- 手动模式：显式传入 `--entity` 和 `--relation`，用于可复现实验。
- 自动模式：不传实体和关系时，先用 entity embedding 找实体候选，再用保守关键词规则推断 KG 关系名，最后执行严格 evidence 检索。
- KG-confirmed mode：同时传入 `--entity`、`--relation`、`--graph-answer`，表示 subject/relation/answer 已由 KG 主流程确认。embedding 只根据这些已确认信息检索辅助证据。

自动关系规则只覆盖当前高置信关系：`providesProduct`、`supports`、`belongsToIndustry`、`servesEnterprise`、`issuesLoan`、`loanToEnterprise`。如果无法判断关系，wrapper 会返回空关系列表，不会自由生成答案。

自动实体选择会先根据问法推断期望实体类型，例如产业问题优先 `IndustrySegment`，银行产品问题优先 `FinancialInstitution`，产品/贷款问题优先 `FinancialProduct`。随后只保留与 top1 实体分数差不超过 `0.05` 的候选，且最多保留 3 个。这样可以减少“科创再贷款”误扩到“科创上市贷款”之类的相邻产品；需要放宽时可调整 `--entity-score-margin` 和 `--max-entity-filters`。

自动关系选择会结合问法和已选实体类型做消歧。例如：

- 产品/提供问法选择 `providesProduct`
- 产业/行业归属问法选择 `belongsToIndustry`
- 产品支持哪些企业选择 `servesEnterprise`
- 金融机构支持哪些企业选择 `issuesLoan`
- 政策支持/再贷款工具问法选择 `supports`

wrapper 输出中的 `is_final_answer` 固定为 `false`，`answer_policy` 会说明 embedding 只作为辅助证据层。`selection_reason` 会记录实体类型过滤、已选实体类型和关系选择原因，便于调试和论文实验说明。

对于“产品支持/服务哪些企业”这类容易混入相邻产品的问题，自动模式只保留 top1 产品实体，避免把“科创再贷款”扩到“科创上市贷款”等相邻产品。

## Evidence Assist / Wrapper Smoke Runner（Optional）

Evidence assist 与 wrapper 目前只保留为 optional / ablation / debug 实验能力，不进入推荐主流程。主流程优先使用实体候选、关系候选后备和 `graph_answers` rerank。

```bash
source configs/experiments/ours_with_embedding_evidence.env
python app/retrieval_only/embedding/embedding_assist_wrapper_smoke_runner.py \
  --cases experiment_notes/embedding_strict_smoke_12.jsonl
```

默认输出：

```text
experiment_notes/embedding_assist_wrapper_smoke_latest.jsonl
experiment_notes/embedding_assist_wrapper_smoke_latest.md
```

这个 runner 只用于小样本辅助候选核验，不运行 V8/V7，不判断最终答案正确性，不作为主流程接入依据。

## Graph Answers Rerank

```bash
source configs/experiments/ours_embedding_full.env
python app/retrieval_only/embedding/graph_answer_reranker.py \
  --query "兰州银行有哪些科技金融产品" \
  --graph-answer "政采e贷" \
  --graph-answer "科创易贷" \
  --graph-answer "人才贷" \
  --top-n 2
```

reranker 的输入必须是 KG/V8 已经返回的 `graph_answers`。它输出：

- `ranked_answers`：包含全部输入答案，只增加 `embedding_score`、`embedding_rank`、`original_rank`
- `display_answers`：按 `top_n` 截取的辅助展示列表
- `is_final_answer=false`

`top_n` 不影响最终答案集合，只影响辅助展示列表。完整答案集合仍以原始 `graph_answers` 为准。

默认展示策略是 `conservative`：

- `ranked_answers` 始终给出 embedding 排序结果，便于分析。
- `display_answers` 只有在 top 分数足够高且与原始第一名差距足够明显时，才采用 embedding 顺序。
- 如果 top 分数低于 `0.45`，或分数差距小于 `0.05`，`display_answers` 保持原始 KG 顺序。

可选参数：

```bash
--display-strategy conservative
--display-strategy embedding
--display-strategy original
--min-top-score 0.45
--min-score-gap 0.05
```

`graph_answers` 可以是字符串，也可以是结构化对象。推荐未来 V8 接入时传结构化对象，例如：

```json
{
  "name": "甘肃洮河拖拉机制造有限公司",
  "type": "Enterprise",
  "relation": "belongsToIndustry",
  "industry": "高端装备制造产业细分",
  "context": "企业属于高端装备制造产业细分"
}
```

结构化上下文可以提升多结果排序鲁棒性，尤其是企业名本身不包含行业语义时。

批量 smoke：

```bash
source configs/experiments/ours_embedding_full.env
python app/retrieval_only/embedding/graph_answer_rerank_smoke_runner.py \
  --cases experiment_notes/graph_answer_rerank_smoke_8.jsonl
```

默认输出：

```text
experiment_notes/graph_answer_rerank_smoke_latest.jsonl
experiment_notes/graph_answer_rerank_smoke_latest.md
```

## 用户问法鲁棒性 Smoke

```bash
source configs/experiments/ours_embedding_full.env
python app/retrieval_only/embedding/embedding_robustness_smoke_runner.py \
  --cases experiment_notes/embedding_robustness_smoke_20.jsonl
```

默认输出：

```text
experiment_notes/embedding_robustness_smoke_latest.jsonl
experiment_notes/embedding_robustness_smoke_latest.md
```

这个 runner 用于观察 embedding 对简称、别名、口语关系、多答案排序和边界问题的辅助潜力。它不运行 V8/V7，也不评估最终答案。

## Text-RAG Baseline

```bash
source configs/experiments/baseline_text_rag_embedding.env
python app/retrieval_only/embedding/text_rag_embedding_baseline.py \
  --query "科技创新再贷款主要支持什么企业"
```

该 baseline 不调用 Neo4j、V8、V7、Type Gate、规则推理、泛关系 fallback 或多跳 planner。它只用于论文中的纯 Text-RAG 对照，不代表主系统答案策略；没有 evidence 时返回无法回答。

## 当前阶段限制

- Embedding 默认关闭。
- 不改变 V8/V7 默认行为。
- 不修改 Neo4j 节点。
- 不创建 Neo4j Vector Index。
- 不修改原始 evidence 文档。
- Embedding assist 不负责最终答案枚举。
- 本阶段不运行 300/1800 评测。

## 后续 V8 接入原则

后续如接入 V8，推荐只接三块主线能力：前置实体候选、关系候选后备、`graph_answers` rerank。Entity grounding 只能为现有主体识别 / Type Gate 提供候选，不能直接覆盖 V8 subject，也不能直接生成最终答案。

推荐的用户问法鲁棒性接入顺序：

```text
用户问题
  -> embedding pre-route entity candidates
       只提供实体候选，不确认 subject
  -> 原有 V8/router/Type Gate 优先识别 qtype、subject、relation
  -> 如果原链路失败、低置信或路径验证失败
       embedding 才提供 relation candidates 作为后备候选
  -> Type Gate + graph path validation + Cypher 确认关系和答案
  -> graph_answers 返回完整答案集合
  -> embedding rerank 对 graph_answers 做辅助排序
```

这个顺序可以概括为：

```text
实体候选前置
关系候选后备
答案排序后置
```

关系识别必须原机制优先。Embedding 只能补充候选，不能独断确认关系。

Evidence assist 不推荐接入主流程。以下接口仅作为 optional / ablation / debug 保留：

```python
from hybrid_embedding_evidence import get_embedding_assist_for_graph_answers

embedding_assist = get_embedding_assist_for_graph_answers(
    question="兰州银行有哪些科技金融产品",
    subject="兰州银行",
    relation="providesProduct",
    graph_answers=["政采e贷"],
    top_k=5,
    min_score=0.60,
)
```

该接口只返回 `embedding_assist` 辅助字段，固定 `is_final_answer=false`，不改变 `graph_answers`、`answer_source`、`route` 或 `final_route`。

候选提议 smoke：

```bash
source configs/experiments/ours_embedding_full.env
python app/retrieval_only/embedding/embedding_pipeline_proposal.py \
  --query "兰州银行给哪些公司放过款"
```

输出中的 `is_confirmed=false`、`requires_graph_validation=true` 表示候选仍必须交给原有机制和图谱路径验证。

# 甘肃省科技金融知识图谱问答系统架构

1. 问题落地：识别实体、关系、目标类型与范围边界，实体归一可由 BGE/FAISS 辅助。
2. Schema 约束：过滤实体类型、关系方向和目标类型不合法的候选。
3. 执行计划：构造直接、反向、开放关系、多跳、规则或证据辅助计划。
4. 执行与校验：在 Neo4j 冻结图谱上执行，检查执行状态、非空性、目标类型与证据轨迹。
5. 输出：返回答案与证据；证据不足、外域或不可回答范围返回边界化拒答。

主要源码：`release_package/05_复现源码/app/retrieval_only/scripts/answer_hybrid_v8_graph_kag_fallback.py`。
Schema：`release_package/05_复现源码/app/schema/`。
Embedding：`release_package/05_复现源码/app/retrieval_only/embedding/`。
基线：`release_package/05_复现源码/tools_baselines/`。

Gold 仅供评估器使用；运行问答不读取 Gold 作为返回答案。
完整图谱、证据语料和正式输出各自保留冻结版本。原始 Gold 与 expanded Gold 同时提供。
指标重算使用 expanded Gold，不调用外部 API，不修改原始预测。

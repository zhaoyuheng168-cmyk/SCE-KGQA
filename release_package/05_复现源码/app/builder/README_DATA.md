# builder/data 数据目录说明

本目录是 Release Runtime 的统一数据中心。

根目录保留若干软链接，用于兼容旧脚本路径：

- nodes_kag.json -> runtime/nodes_kag.json
- edges_kag.json -> runtime/edges_kag.json
- structured_evidence_docs -> evidence/structured_evidence_docs
- structured_evidence_docs_full_auto -> evidence/structured_evidence_docs_full_auto
- relation_chunk_pool -> evidence/relation_chunk_pool
- unstructured_extract_staging -> unstructured/unstructured_extract_staging
- csv -> build_inputs/csv

## 1. runtime/

存放系统运行所需核心图谱 JSON：

- nodes_kag.json
- edges_kag.json

## 2. evidence/

存放结构化证据、全量 evidence 和关系 chunk：

- structured_evidence_docs/
- structured_evidence_docs_full_auto/
- relation_chunk_pool/

## 3. unstructured/

存放非结构化文本抽取和 KAG 同步相关材料：

- unstructured_extract_staging/

## 4. build_inputs/

存放图谱构建输入数据，例如 CSV 标准表。

## 5. build_outputs/

存放图谱构建输出和可追溯材料：

- normalized/
- reports/
- rule_inference/
- edges_splits/

## 6. 设计说明

本目录同时满足两个目标：

1. 作为当前 Release Runtime 的统一数据中心；
2. 保持旧脚本对 builder/data/nodes_kag.json、builder/data/edges_kag.json 等路径的兼容。

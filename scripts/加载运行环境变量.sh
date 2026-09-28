#!/usr/bin/env bash

# ============================================================
# 甘肃科技金融 KGQA Release Runtime 运行环境变量
#
# 用法：
#   source scripts/加载运行环境变量.sh
#
# 注意：
#   必须 source，不能直接 bash 执行。
#   source 后，当前终端后续启动 V8 / 评测脚本都会继承这些环境变量。
# ============================================================

# 1. Neo4j structured 图谱库连接配置
export GTF_NEO4J_URI="bolt://127.0.0.1:7688"
export GTF_NEO4J_USER="neo4j"
export GTF_NEO4J_PASSWORD="${GTF_NEO4J_PASSWORD:-请自行设置}"
export GTF_NEO4J_DATABASE="neo4j"

# 2. V8 / V7 / KAG 功能开关
export GTF_LEVEL2_SUBJECT_SOURCE="graph"
export GTF_ENABLE_KAG_FALLBACK="1"
export GTF_ENABLE_V7_FALLBACK="0"
export GTF_ENABLE_V8_KAG_MULTIHOP_PLANNER="1"
export GTF_V8_KAG_MULTIHOP_MIN_CONF="0.60"

# 3. 评测参数
export EVAL_WORKERS="4"
export EVAL_TIMEOUT="120"

echo "============================================================"
echo "[OK] KGQA Release Runtime 环境变量已加载"
echo "============================================================"
echo "GTF_NEO4J_URI=$GTF_NEO4J_URI"
echo "GTF_NEO4J_USER=$GTF_NEO4J_USER"
echo "GTF_NEO4J_DATABASE=$GTF_NEO4J_DATABASE"

if [ -z "$GTF_NEO4J_PASSWORD" ]; then
  echo "GTF_NEO4J_PASSWORD=未设置"
else
  echo "GTF_NEO4J_PASSWORD=已设置"
fi

echo "GTF_LEVEL2_SUBJECT_SOURCE=$GTF_LEVEL2_SUBJECT_SOURCE"
echo "GTF_ENABLE_KAG_FALLBACK=$GTF_ENABLE_KAG_FALLBACK"
echo "GTF_ENABLE_V7_FALLBACK=$GTF_ENABLE_V7_FALLBACK"
echo "GTF_ENABLE_V8_KAG_MULTIHOP_PLANNER=$GTF_ENABLE_V8_KAG_MULTIHOP_PLANNER"
echo "EVAL_WORKERS=$EVAL_WORKERS"
echo "EVAL_TIMEOUT=$EVAL_TIMEOUT"
echo "============================================================"

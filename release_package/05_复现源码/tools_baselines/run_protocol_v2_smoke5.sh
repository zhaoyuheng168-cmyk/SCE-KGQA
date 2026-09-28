#!/usr/bin/env bash
set -euo pipefail

ROOT="/root/work/GansuTechFinance_KGQA_RELEASE_RUNTIME/deliverables/paper_submission_system_20260522_114215"
cd "$ROOT"
source /home/vipuser/miniconda3/etc/profile.d/conda.sh
conda activate base
source /root/work/GansuTechFinance_KGQA_RELEASE_RUNTIME/scripts/加载运行环境变量.sh
: "${DASHSCOPE_API_KEY:?export DASHSCOPE_API_KEY first}"
export DASHSCOPE_BASE_URL="${DASHSCOPE_BASE_URL:-https://dashscope.aliyuncs.com/compatible-mode/v1}"
export DASHSCOPE_MODEL="qwen3.5-plus"
export GTF_ENABLE_V7_FALLBACK=0

python tools/baselines/audit_comparison_protocol.py

DATASET="experiments/baselines/datasets/smoke_30.csv"
MERGED="experiments/baselines/corpus/merged_rag_corpus.jsonl"
OUT="experiments/baselines/results/protocol_v2_smoke5_qwen35_nothinking"
mkdir -p "$OUT"

run_one() {
  local method="$1"
  local top_k="$2"
  local corpus="${3:-}"
  local output="$OUT/${method}_smoke5.jsonl"
  if [[ -n "$corpus" ]]; then
    python tools/run_baseline_experiment.py --method "$method" --dataset "$DATASET" \
      --corpus "$corpus" --output "$output" --top-k "$top_k" --limit 5 --resume
  else
    python tools/run_baseline_experiment.py --method "$method" --dataset "$DATASET" \
      --output "$output" --top-k "$top_k" --limit 5 --resume
  fi
  python tools/baselines/check_strong_baseline_outputs.py --expected-rows 5 \
    --expected-protocol comparison_protocol_v2_20260607 --expected-model "$DASHSCOPE_MODEL" "$output"
  python tools/baselines/evaluate_baseline_results.py --gold "$DATASET" --pred "$output" \
    --output "$OUT/${method}_smoke5_metrics.json"
}

run_one "llm_only" 0
run_one "naive_bm25_rag" 20 "$MERGED"
run_one "naive_vector_rag" 20 "$MERGED"
run_one "hybrid_rag" 30 "$MERGED"
run_one "text_kg_rag" 30 "$MERGED"
run_one "langchain_rag" 20 "$MERGED"
run_one "llamaindex_rag" 20 "$MERGED"
run_one "kg_context_rag" 80
run_one "entity_linked_graphrag" 80
run_one "rule_based_kgqa" 80
run_one "graph_only_kgqa" 80
run_one "sce_kgqa_full" 50

echo "[DONE] protocol-v2 smoke. Complete LightRAG smoke separately after its index is healthy."

#!/usr/bin/env bash
set -euo pipefail

ROOT="/root/work/GansuTechFinance_KGQA_RELEASE_RUNTIME/deliverables/paper_submission_system_20260522_114215"
cd "$ROOT"

DATASET="experiments/baselines/datasets/gtf_kgqa_1300_formal_expanded_gold.csv"
RESULT_DIR="experiments/baselines/results/formal1300_protocol_v2"
REPORT_DIR="experiments/baselines/reports/formal1300_protocol_v2"
OURS="$RESULT_DIR/sce_kgqa_full_formal1300.jsonl"
mkdir -p "$REPORT_DIR/significance"

predictions=("$RESULT_DIR"/*_formal1300.jsonl)
if [[ -f experiments/external_baselines/results/protocol_v2/lightrag_compact_unified_qwen35_nothinking_nocache_formal1300.jsonl ]]; then
  predictions+=(experiments/external_baselines/results/protocol_v2/lightrag_compact_unified_qwen35_nothinking_nocache_formal1300.jsonl)
fi

python tools/baselines/evaluate_unified_results.py --gold "$DATASET" \
  --output-dir "$REPORT_DIR" "${predictions[@]}"

for baseline in "${predictions[@]}"; do
  [[ "$baseline" == "$OURS" ]] && continue
  name="$(basename "$baseline" .jsonl)"
  python tools/baselines/paired_significance.py --gold "$DATASET" --ours "$OURS" \
    --baseline "$baseline" --output "$REPORT_DIR/significance/${name}_vs_sce.json"
done

python tools/baselines/summarize_engineering_metrics.py "${predictions[@]}" \
  --output-dir "$REPORT_DIR/engineering"
echo "$REPORT_DIR"

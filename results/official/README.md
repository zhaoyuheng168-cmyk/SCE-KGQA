# Official result summaries

The CSV files in this directory were copied from frozen experiment outputs.
They are small publication-oriented summaries, not newly calculated metrics.

| File | Status |
|---|---|
| `main_comparison_formal1300.csv` | Copied unchanged from the final experiment table package |
| `ablation_correctness_summary_public.csv` | Public view of the frozen V8 ablation output; internal provenance-path columns removed, metric values unchanged |

## Frozen-output boundary

The formal result in the main-comparison table is **88.23%** Strict Accuracy.
The ablation table reports **88.31%** for its Full System row. The two values
come from two independent frozen outputs and differ by **1 of 1300 questions**.
They are used only within their respective experiment groups: the main result
is compared with the baselines in the main-comparison table, and every
ablation variant is compared with the Full System row in the ablation table.
The two Full System values must not be mixed or compared across tables. This
is the same reporting boundary used in the submitted manuscript.

The full prediction JSONL files, formal Gold answers, logs and large diagnostic
outputs are intentionally excluded from the showcase.

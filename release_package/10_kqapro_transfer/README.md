# SCE-KGQA: KQA Pro Transfer Reproduction

This repository contains the reproducibility package for transferring the
schema-constrained and evidence-aware candidate selection mechanism of
SCE-KGQA to the public KQA Pro benchmark.

本仓库不声称将原中文科技金融系统零修改迁移到 KQA Pro。实验采用统一的
KoPL semantic parser 生成候选程序，并考察 Schema 约束、执行反馈、非空约束、
问题相关性和事实证据对候选选择的影响。

## Main Results

Frozen holdout: KQA Pro validation indexes `100-11796`, 11,697 questions.
Predictions were generated from question text only and frozen before scoring.

| Method | Exact match | Executable | Non-empty |
|---|---:|---:|---:|
| BART top-1 | 90.485% | 94.127% | 92.400% |
| BART top-5 + Schema | 89.809% | 93.708% | 91.878% |
| BART top-5 + execution feedback | **93.802%** | 97.093% | 96.067% |
| Pre-registered SCE full | 93.220% | 97.093% | 96.067% |

The strongest frozen variant is execution feedback plus the non-empty
constraint. The pre-registered full configuration improves over BART top-1 by
2.735 percentage points, but is not the strongest ablation. This negative
result is intentionally retained.

The gold-KoPL execution result (`99.9576%`) is reported only as an oracle
execution upper bound, not as end-to-end transfer accuracy.

## Repository Contents

```text
scripts/   Question-only generation, Schema reranking, execution and scoring
results/   Aggregate comparison, type analysis and error taxonomy
docs/      Frozen protocols, data record and experimental boundaries
```

The full local delivery includes KQA Pro data, a pinned official parser download with historical SHA256,
frozen question-only inputs, candidates and prediction JSONL under data/, models/ and frozen/.
Optimizer, scheduler, Python environments and caches are excluded.
Only the originally completed migration scope is preserved; no additional transfer result is claimed.
Public redistribution of the parser weights still requires applicable upstream terms.

Frozen nine-variant rescoring (no candidate regeneration):

```powershell
python scripts/score_frozen_ablation_and_types.py
```

## Dependencies

- Python 3.10
- PyTorch with CUDA support
- Transformers
- Hugging Face Hub
- Official KQA Pro baseline executor

Install:

```powershell
python -m pip install -r requirements.txt
git clone https://github.com/shijx12/KQAPro_Baselines.git third_party/KQAPro_Baselines
```

Download the official parser:

```python
from huggingface_hub import snapshot_download

snapshot_download(
    repo_id="THU-KEG/kopl_semantic_parser",
    revision="85f54592b1b5aeea1038e9180fe25098776d24e5",
    local_dir="models/kopl_semantic_parser",
)
```

The local full asset ZIP includes the original KQA Pro data under CC BY-SA 4.0.
The small GitHub code tree uses the separate full asset ZIP.

## Reproduction Stages

1. Create a question-only JSONL:

```powershell
python scripts/prepare_kqapro_blind_questions.py `
  --val path\to\val.json `
  --output work\questions_only.jsonl
```

2. Generate top-5 KoPL candidates:

```powershell
python scripts/generate_kopl_candidates.py `
  --checkpoint models\kopl_semantic_parser `
  --input work\questions_only.jsonl `
  --output work\candidates.jsonl `
  --start-index 100 --limit 0 --num-beams 5 --num-candidates 5
```

3. Apply KB-derived Schema reranking:

```powershell
python scripts/rerank_kopl_candidates_by_schema.py `
  --kb path\to\kb.json `
  --input work\candidates.jsonl `
  --output work\schema_selected.jsonl
```

4. Execute candidates without reading gold labels:

```powershell
python scripts/execute_sce_blind_candidates.py `
  --kb path\to\kb.json `
  --official-repo third_party\KQAPro_Baselines `
  --input work\schema_selected.jsonl `
  --output work\blind_predictions.jsonl
```

5. Score only after predictions are frozen:

```powershell
python scripts/score_kqapro_blind_predictions.py `
  --val path\to\val.json `
  --predictions work\blind_predictions.jsonl `
  --details work\details.csv `
  --summary work\summary.csv
```

Exact frozen hashes are listed in [ARTIFACT_HASHES.md](ARTIFACT_HASHES.md).

## Interpretation Boundary

Valid claim:

> Execution-aware candidate selection improves answer exact match on a frozen
> question-only KQA Pro holdout.

Invalid claim:

> The original SCE-KGQA system was transferred without modification, or the
> 99.9576% oracle score is end-to-end accuracy.

## Third-Party Components

See [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md). No third-party source
code, model weights, or dataset files are redistributed here.

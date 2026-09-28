#!/usr/bin/env python3
"""Select the recovered original June scorer or the previously available version.

The original scorer has now been recovered from the archived research runtime.
Default frozen scoring invokes it unchanged, without a compatibility patch.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'release_package/05_复现源码/blind_tests/blind1200_v3/eval_tools/evaluate_paper_corrected_metrics.py'
AVAILABLE=SOURCE.with_name('evaluate_paper_corrected_metrics_available_20260909.py')


def main() -> None:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',required=True)
    parser.add_argument('--result',required=True)
    parser.add_argument('--out-dir',required=True)
    parser.add_argument('--protocol',choices=['frozen-20260607','available-scorer'],default='frozen-20260607')
    args=parser.parse_args()
    chosen=SOURCE if args.protocol=='frozen-20260607' else AVAILABLE
    spec=importlib.util.spec_from_file_location('chosen_task_aware_scorer',chosen)
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    sys.argv=[str(chosen),'--source',args.source,'--result',args.result,'--out-dir',args.out_dir]
    module.main()
    provenance={
        'protocol':args.protocol,
        'implementation':'recovered original June scorer, unchanged' if args.protocol=='frozen-20260607' else 'previously available scorer, unchanged',
        'basis':'server archive provenance and full row-level verification; see docs/RECOVERED_SERVER_ASSETS.json',
        'predictions_or_gold_modified':False,
    }
    (Path(args.out_dir)/'EVALUATOR_PROVENANCE.json').write_text(json.dumps(provenance,indent=2)+'\n',encoding='utf-8')


if __name__=='__main__':
    main()

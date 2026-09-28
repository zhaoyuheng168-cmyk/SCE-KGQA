#!/usr/bin/env python3
"""Recompute frozen strict/task-aware scores without a model or API key."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'release_package' / '05_复现源码'
DATA = ROOT / 'release_package' / '04_数据与知识资源'
RESULTS = ROOT / 'release_package' / '03_正式结果' / '对比实验' / 'formal1300_protocol_v2'


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--method', default='sce_kgqa_full')
    parser.add_argument('--output', type=Path, default=ROOT / 'runtime_data' / 'recomputed_metrics')
    parser.add_argument('--protocol', choices=['frozen-20260607', 'available-scorer'], default='frozen-20260607')
    args = parser.parse_args()
    if '/' in args.method or '\\' in args.method or '..' in args.method:
        parser.error('Use a method name, not a path')
    pred = RESULTS / f'{args.method}_formal1300.jsonl'
    if not pred.is_file():
        parser.error(f'Prediction file does not exist for method {args.method}')
    args.output.mkdir(parents=True, exist_ok=True)
    strict = args.output / args.method / 'strict_metrics.json'
    gold = DATA / 'benchmark' / 'gtf_kgqa_1300_formal_expanded_gold.csv'
    subprocess.run([sys.executable, str(SOURCE/'tools_baselines/evaluate_baseline_results.py'),
                    '--gold', str(gold), '--pred', str(pred), '--output', str(strict)], check=True,
                   stdout=subprocess.DEVNULL)
    # The frozen task-aware inputs preserve the original route/refusal fields.
    frozen = ROOT/'release_package/02_实验协议与报告/formal1300_protocol_v2'/args.method/'task_aware_input.csv'
    task = args.output / args.method / 'task_aware_metrics'
    subprocess.run([sys.executable, str(ROOT/'tools/evaluate_frozen_task_aware.py'),
                    '--source', str(gold), '--result', str(frozen), '--out-dir', str(task),
                    '--protocol', args.protocol], check=True,
                   stdout=subprocess.DEVNULL)
    a = json.loads(strict.read_text(encoding='utf-8'))
    b = json.loads((task/'paper_corrected_metrics_summary.json').read_text(encoding='utf-8'))
    print(json.dumps({'method':args.method,'protocol':args.protocol,'strict_rows':a['total'],'strict_accuracy':a['accuracy'],
                      'task_aware_rows':b.get('total'),'task_aware_accuracy':b.get('paper_corrected_accuracy'),
                      'output':str(args.output)},ensure_ascii=False,indent=2))


if __name__ == '__main__':
    main()

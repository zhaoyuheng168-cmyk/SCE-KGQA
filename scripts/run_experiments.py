#!/usr/bin/env python3
"""Portable launch plans for the original experiments. Use --execute to run."""
import argparse
import csv
import json
import subprocess
import sys
from pathlib import Path

from run_qa import ROOT, reproduction_env

def normalized_natural(source, target):
    rows = list(csv.DictReader(source.open(encoding='utf-8-sig', newline='')))
    for row in rows:
        row['question_id'] = row['qid']
        row['gold_items'] = row['gold_answers']
        row.setdefault('should_refuse', 'no')
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open('w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader(); writer.writerows(rows)
    return target

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--suite', choices=['main', 'ablation', 'natural', 'stress', 'kqapro-frozen'], required=True)
    parser.add_argument('--method', help='Run one original main comparison method')
    parser.add_argument('--workers', type=int, default=4)
    parser.add_argument('--limit', type=int, default=0)
    parser.add_argument('--execute', action='store_true')
    args = parser.parse_args()
    runtime = ROOT / 'runtime_data/repro_runtime'
    output = ROOT / 'runtime_data/new_experiments' / args.suite
    env = reproduction_env(runtime)
    env['EVAL_WORKERS'] = str(args.workers)
    commands = []
    cwd = runtime
    if args.suite == 'main':
        methods = [x['method'] for x in json.loads((ROOT / 'SCORING_VALIDATION.json').read_text(encoding='utf-8'))['methods']]
        if args.method:
            if args.method not in methods: parser.error('Unknown formal comparison method')
            methods = [args.method]
        for method in methods:
            commands.append([sys.executable, str(runtime / 'tools/run_baseline_experiment.py'),
                '--method', method, '--output', str(output / f'{method}.jsonl'),
                '--workers', str(args.workers), '--limit', str(args.limit), '--resume', '--retry-errors'])
        commands.append([sys.executable, str(runtime / 'tools/baselines/evaluate_unified_results.py'),
            '--gold', str(runtime / 'experiments/baselines/datasets/gtf_kgqa_1300_formal_expanded_gold.csv'),
            '--output-dir', str(output / 'metrics'), *[str(output / f'{method}.jsonl') for method in methods]])
    elif args.suite in {'ablation', 'natural'}:
        selected = ['full_embedding', 'without_embedding', 'without_reverse_relation', 'without_multihop',
                    'without_rule_reasoning', 'without_generic_relation', 'without_refusal_gate']
        command = [sys.executable, str(runtime / 'tools/run_ablation_experiment.py'),
            '--experiments', *selected, '--workers', str(args.workers), '--limit', str(args.limit), '--out-root', str(output)]
        if args.suite == 'natural':
            source = ROOT / 'release_package/09_20260614_最终增补/independent_eval/natural_questions_20260611/data/independent_natural_questions_100.csv'
            dataset = output / 'natural100_normalized.csv'
            if args.execute: normalized_natural(source, dataset)
            command = [sys.executable, str(runtime / 'tools/run_ablation_experiment.py'),
                '--experiments', 'full_embedding', 'without_embedding', 'without_generic_relation', 'without_kag_evidence',
                '--workers', str(args.workers), '--limit', str(args.limit), '--out-root', str(output),
                '--dataset', str(dataset), '--gold', str(dataset)]
        commands.append(command)
    elif args.suite == 'stress':
        if args.limit: parser.error('Original stress runners evaluate all 100 questions; omit --limit')
        for name in ['run_formal100_compare_ablation_workers4.py', 'run_formal100_bm25_fixed_workers4.py']:
            commands.append([sys.executable, str(runtime / 'independent_eval/functional_stress_20260612_v6' / name)])
    else:
        cwd = ROOT / 'release_package/10_kqapro_transfer'
        commands.append([sys.executable, str(cwd / 'scripts/score_frozen_ablation_and_types.py')])
    print(json.dumps({'suite': args.suite, 'execute': args.execute, 'commands': commands,
                     'scope': 'original completed experiments; no new transfer experiment'}, ensure_ascii=False, indent=2))
    if not args.execute: return 0
    if args.suite != 'kqapro-frozen' and not (runtime / 'tools/run_baseline_experiment.py').is_file():
        parser.error('First run python scripts/prepare_runtime.py')
    output.mkdir(parents=True, exist_ok=True)
    for command in commands:
        subprocess.run(command, cwd=cwd, env=env, check=True)
    return 0

if __name__ == '__main__':
    raise SystemExit(main())

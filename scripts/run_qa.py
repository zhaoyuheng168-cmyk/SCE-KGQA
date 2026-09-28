#!/usr/bin/env python3
"""Run the actual V8 backend from the prepared research runtime."""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def reproduction_env(runtime: Path) -> dict[str, str]:
    load_local_env(ROOT / '.env')
    env = os.environ.copy()
    flag_path = ROOT / 'configs' / 'runtime_flags.json'
    if flag_path.exists():
        for key, value in json.loads(flag_path.read_text(encoding='utf-8')).items():
            env.setdefault(key, str(value))
    env.setdefault('PYTHONIOENCODING', 'utf-8')
    env.setdefault('GTF_NEO4J_URI', 'bolt://127.0.0.1:7688')
    env.setdefault('GTF_ENABLE_V7_FALLBACK', '0')
    env.setdefault('GTF_LEVEL2_SUBJECT_SOURCE', 'graph')
    model = env.get('GTF_EMBEDDING_MODEL_NAME', 'BAAI/bge-small-zh-v1.5')
    bundled = ROOT / 'release_package/04_数据与知识资源/models/bge-small-zh-v1.5'
    if model in {'', 'BAAI/bge-small-zh-v1.5', 'runtime_data/models/bge-small-zh-v1.5'} and bundled.is_dir():
        model = str(bundled)
    elif Path(model).is_absolute() or (ROOT / model).exists():
        model = str((ROOT / model).resolve())
    env['GTF_EMBEDDING_MODEL_NAME'] = model
    env.setdefault('GTF_KAG_CONFIG_PATH', str(runtime / 'app' / 'kag_config.yaml'))
    return env


def load_local_env(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding='utf-8-sig').splitlines():
        line = line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        key, value = line.split('=', 1)
        key = key.strip()
        if not key.replace('_', '').isalnum():
            raise ValueError('Invalid environment variable name in local configuration')
        os.environ.setdefault(key, value.strip().strip('\"\''))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('question', nargs='?')
    parser.add_argument('--runtime', type=Path, default=ROOT / 'runtime_data' / 'repro_runtime')
    parser.add_argument('--check', action='store_true', help='Check required files without contacting a service.')
    args = parser.parse_args()
    load_local_env(ROOT / '.env')
    runtime = args.runtime.resolve()
    entry = runtime / 'app' / 'retrieval_only' / 'scripts' / 'answer_hybrid_v8_graph_kag_fallback.py'
    checks = {
        'backend': entry.is_file(),
        'evidence': (runtime / 'app' / 'builder' / 'data' / 'evidence').is_dir(),
        'entity_index': (runtime / 'app' / 'retrieval_only' / 'embedding_indexes' / 'entity_names').is_dir(),
        'gold': (runtime / 'experiments' / 'baselines' / 'datasets' / 'gtf_kgqa_1300_formal.csv').is_file(),
    }
    if args.check:
        print(json.dumps(checks, ensure_ascii=False, indent=2))
        return 0 if all(checks.values()) else 1
    if not checks['backend']:
        parser.error('Prepare the runtime first: python scripts/prepare_runtime.py')
    if not args.question:
        parser.error('Provide a question or use --check')
    env = reproduction_env(runtime)
    return subprocess.run([sys.executable, str(entry), args.question], cwd=runtime, env=env).returncode


if __name__ == '__main__':
    raise SystemExit(main())

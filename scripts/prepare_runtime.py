#!/usr/bin/env python3
"""Assemble a portable runtime from the frozen, public research assets."""
from __future__ import annotations

import argparse
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'release_package' / '05_复现源码'
DATA = ROOT / 'release_package' / '04_数据与知识资源'


def prepare(destination: Path) -> Path:
    destination = destination.resolve()
    destination.mkdir(parents=True, exist_ok=True)
    shutil.copytree(SOURCE / 'app', destination / 'app', dirs_exist_ok=True,
                    ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    shutil.copytree(SOURCE / 'tools_baselines', destination / 'tools' / 'baselines', dirs_exist_ok=True)
    if (SOURCE / 'tools').exists():
        shutil.copytree(SOURCE / 'tools', destination / 'tools', dirs_exist_ok=True,
                        ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    for folder in ['experiments', 'blind_tests']:
        if (SOURCE / folder).exists():
            shutil.copytree(SOURCE / folder, destination / folder, dirs_exist_ok=True)
    shutil.copytree(DATA / 'benchmark', destination / 'experiments' / 'baselines' / 'datasets', dirs_exist_ok=True)
    shutil.copytree(DATA / 'corpus', destination / 'experiments' / 'baselines' / 'corpus', dirs_exist_ok=True)
    shutil.copytree(DATA / 'runtime_data' / 'evidence', destination / 'app' / 'builder' / 'data' / 'evidence', dirs_exist_ok=True)
    shutil.copytree(DATA / 'runtime_data' / 'kag_runtime', destination / 'app' / 'builder' / 'data' / 'runtime', dirs_exist_ok=True)
    for name in ['evidence', 'kag_runtime']:
        shutil.copytree(DATA / 'runtime_data' / name, destination / 'runtime_data' / name, dirs_exist_ok=True)
    if (DATA / 'models').exists():
        shutil.copytree(DATA / 'models', destination / 'runtime_data' / 'models', dirs_exist_ok=True)
    supplements = ROOT / 'release_package' / '09_20260614_最终增补' / 'independent_eval'
    if supplements.exists():
        shutil.copytree(supplements, destination / 'independent_eval', dirs_exist_ok=True,
                        ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    staging = DATA / 'unstructured_pipeline_snapshot'
    for batch in ['batch2_60', 'batch3_large_90']:
        if (staging / batch / 'kag_sync').is_dir():
            shutil.copytree(staging / batch / 'kag_sync', destination / 'runtime_data' / 'evidence' /
                            'unstructured_extract_staging' / batch / 'kag_sync', dirs_exist_ok=True)
    outputs = staging / 'outputs'
    if outputs.exists():
        shutil.copytree(outputs, destination / 'runtime_data' / 'evidence' /
                        'unstructured_extract_staging' / 'outputs', dirs_exist_ok=True)
    example = SOURCE / 'app' / 'kag_config.example.yaml'
    if example.exists() and not (destination / 'app' / 'kag_config.yaml').exists():
        shutil.copy2(example, destination / 'app' / 'kag_config.yaml')
    for path in SOURCE.glob('*.py'):
        shutil.copy2(path, destination / 'tools' / path.name)
    return destination


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--destination', type=Path, default=ROOT / 'runtime_data' / 'repro_runtime')
    args = parser.parse_args()
    path = prepare(args.destination)
    print(f'Runtime prepared: {path}')


if __name__ == '__main__':
    main()

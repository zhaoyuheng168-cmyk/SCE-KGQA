#!/usr/bin/env python3
"""Download pinned original embedding or KoPL inference weights and verify hashes."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, default=ROOT / 'models' / 'MODEL_MANIFEST.json')
    parser.add_argument('--output', type=Path)
    parser.add_argument('--model', choices=['embedding', 'kopl'], default='embedding')
    parser.add_argument('--show', action='store_true', help='Print model identity without downloading.')
    args = parser.parse_args()
    all_models = json.loads(args.manifest.read_text(encoding='utf-8'))
    info = all_models['kopl_parser' if args.model == 'kopl' else 'embedding_model']
    if args.output is None:
        args.output = ROOT / info['bundled_directory']
    if args.show:
        print(json.dumps(info, ensure_ascii=False, indent=2))
        return
    if not info.get('revision') or info['revision'] in {'main', 'UNKNOWN'}:
        parser.error('A full immutable upstream revision is required in MODEL_MANIFEST.json')
    try:
        from huggingface_hub import snapshot_download
    except ImportError:
        parser.error('Install huggingface-hub or the optional embedding requirements first.')
    snapshot_download(repo_id=info['repo_id'], revision=info['revision'],
                      local_dir=args.output, allow_patterns=
                      ['config.json', 'merges.txt', 'vocab.json', 'pytorch_model.bin', 'README.md']
                      if args.model == 'kopl' else None,
                      ignore_patterns=['pytorch_model.bin'] if args.model == 'embedding' else None)
    weight = args.output / ('pytorch_model.bin' if args.model == 'kopl' else 'model.safetensors')
    expected_weight = info.get('historical_pytorch_sha256') if args.model == 'kopl' else info.get('historical_safetensors_sha256')
    if expected_weight:
        h = hashlib.sha256()
        with weight.open('rb') as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b''): h.update(chunk)
        if h.hexdigest() != expected_weight:
            raise SystemExit('Downloaded weight does not match the recorded historical SHA256')
    records = []
    for path in sorted(args.output.rglob('*')):
        if path.is_file() and '.cache' not in path.parts:
            with path.open('rb') as handle:
                digest = hashlib.file_digest(handle, 'sha256').hexdigest() if hasattr(hashlib, 'file_digest') else None
            if digest is None:
                h = hashlib.sha256()
                with path.open('rb') as handle:
                    for chunk in iter(lambda: handle.read(1024 * 1024), b''): h.update(chunk)
                digest = h.hexdigest()
            records.append({'path': path.relative_to(args.output).as_posix(), 'sha256': digest})
    (args.output / 'DOWNLOAD_MANIFEST.json').write_text(json.dumps({'model':info,'files':records}, indent=2)+'\n',encoding='utf-8')
    print(f'Downloaded {info["repo_id"]} at revision {info["revision"]}')


if __name__ == '__main__':
    main()

#!/usr/bin/env python3
"""Verify and restore the matching local full-asset ZIP into this checkout."""
from __future__ import annotations
import argparse
import hashlib
import json
import shutil
import zipfile
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive', type=Path, help='Existing local ZIP; omitted to download from ASSETS.json')
    parser.add_argument('--sha256', help='Expected SHA256; defaults to ASSETS.json')
    args = parser.parse_args()
    index_path = ROOT / 'ASSETS.json'
    index = json.loads(index_path.read_text(encoding='utf-8')) if index_path.exists() else {}
    if args.archive is None:
        from urllib.request import urlopen
        url = index.get('download_url')
        if not url or not url.startswith('https://github.com/zhaoyuheng168-cmyk/SCE-KGQA/releases/download/'):
            parser.error('Missing authorized release URL in ASSETS.json')
        directory = ROOT / 'runtime_data/downloads'
        directory.mkdir(parents=True, exist_ok=True)
        args.archive = directory / index['archive']
        if not args.archive.exists():
            partial = args.archive.with_suffix('.zip.part')
            with urlopen(url, timeout=120) as response, partial.open('wb') as output:
                shutil.copyfileobj(response, output, length=1024*1024)
            partial.replace(args.archive)
    archive = args.archive.resolve(strict=True)
    expected = args.sha256 or index.get('sha256')
    if not expected or digest(archive) != expected:
        raise SystemExit('Missing expected SHA256 or archive checksum mismatch; no files extracted.')
    with zipfile.ZipFile(archive) as z:
        members = z.infolist()
        names = [m.filename for m in members]
        if len(names) != len(set(names)):
            raise SystemExit('Duplicate archive members; no files extracted.')
        for m in members:
            name = PurePosixPath(m.filename)
            if (name.is_absolute() or '..' in name.parts or '\\' in m.filename
                    or ':' in m.filename or m.filename.startswith('/')
                    or any(p in {'.git', '.env'} for p in name.parts)
                    or name.suffix.lower() in {'.pem', '.key'}):
                raise SystemExit('Unsafe archive member; no files extracted.')
            dst = (ROOT / Path(*name.parts)).resolve()
            try:
                dst.relative_to(ROOT)
            except ValueError:
                raise SystemExit('Archive path escapes checkout; no files extracted.')
        if z.testzip() is not None:
            raise SystemExit('Archive CRC error; no files extracted.')
        for m in members:
            dst = ROOT / Path(*PurePosixPath(m.filename).parts)
            if m.is_dir():
                dst.mkdir(parents=True, exist_ok=True)
            else:
                dst.parent.mkdir(parents=True, exist_ok=True)
                with z.open(m) as source, dst.open('wb') as target:
                    shutil.copyfileobj(source, target)
    print(json.dumps({'archive': archive.name, 'extracted_members': len(members),
                      'destination': str(ROOT)}, ensure_ascii=False))


if __name__ == '__main__':
    main()

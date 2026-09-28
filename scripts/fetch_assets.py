#!/usr/bin/env python3
"""Download/verify full assets, join release volumes, and restore research assets."""
import argparse
import hashlib
import json
import re
import shutil
import zipfile
from pathlib import Path, PurePosixPath
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
RELEASE_PREFIX = 'https://github.com/zhaoyuheng168-cmyk/SCE-KGQA/releases/download/'

def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda:f.read(1024*1024), b''): h.update(block)
    return h.hexdigest()

def download(url, destination):
    if not url or not url.startswith(RELEASE_PREFIX):
        raise ValueError('Missing authorized project release URL')
    temporary = destination.with_name(destination.name+'.download')
    with urlopen(url, timeout=120) as response, temporary.open('wb') as output:
        shutil.copyfileobj(response, output, length=1024*1024)
    temporary.replace(destination)

def fetch(index, directory):
    directory.mkdir(parents=True, exist_ok=True)
    name = index['archive']
    if not re.fullmatch(r'[A-Za-z0-9_.-]+\.zip', name):
        raise ValueError('Unsafe archive name')
    archive = directory/name
    if archive.exists() and digest(archive)==index['sha256']: return archive
    parts = index.get('parts', [])
    if parts:
        paths = []
        seen = set()
        for number, part in enumerate(parts, 1):
            expected_name = f'{name}.part{number:02d}'
            if part['name'] != expected_name or part['name'] in seen:
                raise ValueError('Invalid or duplicate volume sequence')
            seen.add(part['name'])
            target = directory/part['name']
            if not target.exists() or digest(target)!=part['sha256']:
                print(f'Downloading volume {number}/{len(parts)}: {part["name"]}', flush=True)
                download(part['download_url'], target)
            if target.stat().st_size!=part['bytes'] or digest(target)!=part['sha256']:
                raise ValueError('Volume size or SHA256 mismatch')
            paths.append(target)
        temporary = archive.with_name(archive.name+'.download')
        with temporary.open('wb') as output:
            for target in paths:
                with target.open('rb') as source: shutil.copyfileobj(source,output,length=1024*1024)
        if digest(temporary)!=index['sha256']:
            raise ValueError('Combined full archive SHA256 mismatch')
        temporary.replace(archive)
    else:
        download(index.get('download_url'), archive)
    return archive

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive', type=Path, help='Existing full ZIP, otherwise auto-download')
    parser.add_argument('--sha256', help='Defaults to ASSETS.json')
    args = parser.parse_args()
    index = json.loads((ROOT/'ASSETS.json').read_text(encoding='utf-8'))
    archive = args.archive.resolve(strict=True) if args.archive else fetch(index,ROOT/'runtime_data/downloads')
    expected = args.sha256 or index.get('sha256')
    if not expected or digest(archive)!=expected:
        raise SystemExit('Full archive checksum mismatch; no files restored')
    with zipfile.ZipFile(archive) as z:
        members = z.infolist()
        if len(members)!=len({m.filename for m in members}):
            raise SystemExit('Duplicate archive members')
        for m in members:
            name = PurePosixPath(m.filename)
            if (name.is_absolute() or '..' in name.parts or '\\' in m.filename or ':' in m.filename
                    or any(p in {'.git','.env'} for p in name.parts) or name.suffix.lower() in {'.pem','.key'}):
                raise SystemExit('Unsafe archive member')
            (ROOT/Path(*name.parts)).resolve().relative_to(ROOT.resolve())
        if z.testzip() is not None: raise SystemExit('Archive CRC mismatch')
        restored = 0
        # Git manages launchers and documentation. Restore the full research tree only.
        for m in members:
            name = PurePosixPath(m.filename)
            if not name.parts or name.parts[0]!='release_package': continue
            dst = ROOT/Path(*name.parts)
            if m.is_dir(): dst.mkdir(parents=True,exist_ok=True)
            else:
                dst.parent.mkdir(parents=True,exist_ok=True)
                with z.open(m) as source,dst.open('wb') as target: shutil.copyfileobj(source,target)
                restored += 1
    print(json.dumps({'archive':archive.name,'research_files_restored':restored,'destination':str(ROOT)},ensure_ascii=False))

if __name__=='__main__': main()

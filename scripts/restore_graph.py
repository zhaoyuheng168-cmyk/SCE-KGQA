#!/usr/bin/env python3
"""Restore the bundled graph with credentials read from local .env/environment."""
from __future__ import annotations
import os
import subprocess
import sys
from pathlib import Path
from run_qa import load_local_env

ROOT=Path(__file__).resolve().parents[1]

def main() -> int:
    load_local_env(ROOT/'.env')
    if not os.environ.get('GTF_NEO4J_PASSWORD'):
        raise SystemExit('Set GTF_NEO4J_PASSWORD in your local .env first.')
    return subprocess.run([sys.executable,str(ROOT/'tools/restore_neo4j_from_jsonl.py'),*sys.argv[1:]],env=os.environ.copy()).returncode

if __name__ == '__main__':
    raise SystemExit(main())

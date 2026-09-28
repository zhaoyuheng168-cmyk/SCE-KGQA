#!/usr/bin/env python3
"""Prepare GraphRAG input workspace without indexing."""
from __future__ import annotations
import argparse, shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
BASE = ROOT / "experiments/external_baselines"

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--mode", choices=["smoke","full"], required=True)
    p.add_argument("--variant", choices=["raw","natural"], default="raw")
    a=p.parse_args()
    suffix="_natural" if a.variant=="natural" else ""
    source=BASE/"common/corpus"/(("smoke_docs" if a.mode=="smoke" else "all_docs")+suffix)
    if not source.exists():
        raise SystemExit(f"Corpus directory does not exist: {source}")
    target=BASE/f"microsoft_graphrag/workspace/{a.mode}{suffix}"
    inp=target/"input"; inp.mkdir(parents=True, exist_ok=True)
    for old in inp.glob("*.txt"): old.unlink()
    for doc in source.glob("*.txt"): shutil.copy2(doc, inp/doc.name)
    (target/"ENVIRONMENT.template").write_text(
        "DASHSCOPE_API_KEY=<export-in-shell-only>\nDASHSCOPE_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1\nDASHSCOPE_MODEL=qwen-plus\n",
        encoding="utf-8")
    (target/"README.md").write_text("Run `graphrag init --root .` inside this workspace, then configure settings.yaml for an OpenAI-compatible provider before indexing.\n", encoding="utf-8")
    print(target)
if __name__=="__main__": main()

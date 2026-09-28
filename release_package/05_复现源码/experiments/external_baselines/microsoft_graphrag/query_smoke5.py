#!/usr/bin/env python3
"""Query Microsoft GraphRAG CLI for five question-only rows."""
from __future__ import annotations
import csv, json, subprocess, time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]; BASE=ROOT/"experiments/external_baselines"
questions=BASE/"common/smoke_questions.csv"; ws=BASE/"microsoft_graphrag/workspace/smoke"
out=BASE/"results"/f"microsoft_graphrag_smoke5_{time.strftime('%Y%m%d_%H%M%S')}.jsonl"; out.parent.mkdir(parents=True,exist_ok=True)
with questions.open(encoding="utf-8-sig",newline="") as f, out.open("w",encoding="utf-8") as dst:
 for row in csv.DictReader(f):
  start=time.time(); proc=subprocess.run(["graphrag","query","--root",str(ws),"--method","local","--response-type","Single Sentence","--query",row["question"]],capture_output=True,text=True)
  dst.write(json.dumps({"question_id":row["question_id"],"question":row["question"],"method":"microsoft_graphrag","raw_answer":proc.stdout.strip(),"prediction":proc.stdout.strip(),"returncode":proc.returncode,"latency_ms":int((time.time()-start)*1000),"stderr":proc.stderr[-500:]},ensure_ascii=False)+"\n")
print(out)

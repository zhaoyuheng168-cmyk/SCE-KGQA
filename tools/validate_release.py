#!/usr/bin/env python3
"""Validate full Gold, graph and corpus integrity with the Python standard library."""
from __future__ import annotations
import ast
import csv
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/'release_package/04_数据与知识资源'

def jsonl(path: Path):
    with path.open(encoding='utf-8') as handle:
        for line in handle:
            if line.strip(): yield json.loads(line)

def main() -> int:
    checks=[]
    def check(name,ok,**details):
        checks.append({'check':name,'passed':bool(ok),**details})
    gold_sets=[]
    for filename in ['gtf_kgqa_1300_formal.csv','gtf_kgqa_1300_formal_expanded_gold.csv']:
        with (DATA/'benchmark'/filename).open(encoding='utf-8-sig',newline='') as f:rows=list(csv.DictReader(f))
        ids=[r['question_id'] for r in rows]
        check(filename,len(rows)==1300 and len(set(ids))==1300 and all(r['question'].strip() for r in rows),rows=len(rows),unique_ids=len(set(ids)))
        gold_sets.append(set(ids))
    check('gold_id_alignment',gold_sets[0]==gold_sets[1])
    export=DATA/'runtime_data/neo4j_export'
    nodes=list(jsonl(export/'nodes.jsonl'))
    ids={str(n['id']) for n in nodes}
    relations=list(jsonl(export/'relationships.jsonl'))
    dangling=sum(str(r['start_id']) not in ids or str(r['end_id']) not in ids for r in relations)
    check('graph_nodes',len(nodes)==1707 and len(ids)==1707,count=len(nodes),unique_ids=len(ids))
    check('graph_relationships',len(relations)==31018 and dangling==0,count=len(relations),dangling_endpoints=dangling)
    for name,expected in [('kg_triples_corpus.jsonl',22152),('evidence_corpus.jsonl',5612),('merged_rag_corpus.jsonl',27764)]:
        rows=list(jsonl(DATA/'corpus'/name))
        doc_ids=[x.get('doc_id') for x in rows]
        check(name,len(rows)==expected and len(set(doc_ids))==expected,count=len(rows),unique_ids=len(set(doc_ids)))
    syntax_errors=[]
    files=[]
    for folder in [ROOT/'tools',ROOT/'scripts',ROOT/'app',ROOT/'release_package/05_复现源码']:
        for p in folder.rglob('*.py'):
            if '__pycache__' in p.parts:continue
            files.append(p)
            try:ast.parse(p.read_text(encoding='utf-8-sig'),filename=p.name)
            except SyntaxError as e:syntax_errors.append({'file':p.relative_to(ROOT).as_posix(),'line':e.lineno,'message':e.msg})
    check('python_syntax',not syntax_errors,files=len(files),errors=syntax_errors)
    report={'passed':all(x['passed'] for x in checks),'checks':checks}
    print(json.dumps(report,ensure_ascii=False,indent=2))
    return 0 if report['passed'] else 1

if __name__=='__main__':
    raise SystemExit(main())

#!/usr/bin/env python3
"""Verify strict, task-aware and row-level scores against every frozen baseline."""
from __future__ import annotations
import csv
import json
import math
import subprocess
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
FROZEN=ROOT/'release_package/02_实验协议与报告/formal1300_protocol_v2'

def read_rows(path):
    with path.open(encoding='utf-8-sig',newline='') as f:return {r['question_id']:r for r in csv.DictReader(f)}

def main() -> int:
    results=[]
    for method in sorted(FROZEN.iterdir()):
        if not method.is_dir() or not (method/'strict_metrics.json').exists():continue
        output=ROOT/'runtime_data/recomputed_metrics_all'
        proc=subprocess.run([sys.executable,str(ROOT/'scripts/recompute_metrics.py'),'--method',method.name,'--output',str(output)],capture_output=True,text=True,encoding='utf-8')
        if proc.returncode:
            results.append({'method':method.name,'passed':False,'error':'recomputation failed','returncode':proc.returncode});continue
        differences=[]
        for name,keys in [('strict_metrics.json',['total','accuracy','precision','recall','f1','refusal_accuracy']),
                          ('task_aware_metrics/paper_corrected_metrics_summary.json',['total','paper_corrected_passed','paper_corrected_accuracy','non_refusal_macro_precision','non_refusal_macro_recall','non_refusal_macro_f1'])]:
            old=json.loads((method/name).read_text(encoding='utf-8'))
            new=json.loads((output/method.name/name).read_text(encoding='utf-8'))
            for key in keys:
                if not math.isclose(float(old[key]),float(new[key]),rel_tol=1e-12,abs_tol=1e-12):differences.append({'file':name,'field':key,'frozen':old[key],'recomputed':new[key]})
        rel='task_aware_metrics/paper_corrected_metrics_rows.csv'
        oldrows=read_rows(method/rel);newrows=read_rows(output/method.name/rel)
        if set(oldrows)!=set(newrows):differences.append({'field':'row_id_coverage'})
        row_differences=[]
        for qid,a in oldrows.items():
            b=newrows.get(qid,{})
            for key in ['paper_passed','gold_count','pred_count','hit_count','paper_precision','paper_recall','paper_f1']:
                av=a.get(key);bv=b.get(key)
                if av==bv:continue
                try:equal=math.isclose(float(av),float(bv),rel_tol=1e-12,abs_tol=1e-12)
                except (TypeError,ValueError):equal=False
                if not equal:row_differences.append({'qid':qid,'field':key,'frozen':av,'recomputed':bv})
        results.append({'method':method.name,'passed':not differences and not row_differences,'rows':len(oldrows),
                        'summary_differences':differences,'row_differences':row_differences})
    report={'passed':bool(results) and all(x['passed'] for x in results),'methods':results,
            'scorer_provenance':'Original June scorer recovered from archived research runtime and invoked unchanged.'}
    path=ROOT/'SCORING_VALIDATION.json'
    path.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'passed':report['passed'],'methods':len(results),'rows_checked':sum(x.get('rows',0) for x in results),
                      'failed_methods':[x['method'] for x in results if not x['passed']]},ensure_ascii=False))
    return 0 if report['passed'] else 1

if __name__=='__main__':
    raise SystemExit(main())

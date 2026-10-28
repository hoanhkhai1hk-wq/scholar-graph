"""Actual resident production path, including lock/IPC, with the normal five-second budget."""
import json
from pathlib import Path
import sys
import time

ROOT=Path(__file__).resolve().parents[2]; sys.path.insert(0,str(ROOT/'backend'))
from scholar_graph.qa_retrieval import LocalReranker
from scholar_graph.rerank_worker import resident_worker,close_workers

if __name__=='__main__':
    base=ROOT/'data/item02-20261028'; payload=json.loads((base/'rerank-pool.json').read_text(encoding='utf-8'))
    python=ROOT/'data/module-four-runtime/.venv/Scripts/python.exe'; model=ROOT/'data/module-four-models/bge-reranker-large'
    service=LocalReranker(base,python,model,resident=True)
    chunks=[{'chunk_id':x['id'],'text':x['text']} for x in payload['items']]
    report={'budget_seconds':5,'candidate_count':10,'samples':[]}
    for phase in ['cold','warm-1','warm-2','warm-3']:
        if phase=='warm-1': report['startup']=resident_worker(python,model).prepare(timeout=90)
        started=time.perf_counter(); order,info=service.order(payload['question'],chunks)
        row={'phase':phase,'elapsed_seconds':round(time.perf_counter()-started,6),'accepted':order is not None,'metadata':info,'order':order}
        report['samples'].append(row)
        (base/'rerank-production-budget.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
        print(json.dumps({k:v for k,v in row.items() if k!='order'},ensure_ascii=False),flush=True)
    close_workers()

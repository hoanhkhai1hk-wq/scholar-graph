"""Diagnostic complete top-ten timing, never a production budget override."""
import hashlib
import json
import os
from pathlib import Path
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'backend'))
from scholar_graph.api_repository import ApiRepository
from scholar_graph.qa_retrieval import qa_retriever
from scholar_graph.rerank_worker import close_workers, resident_worker
from scholar_graph.validation import ContractGate


def main():
    source_ids=json.loads((ROOT/'data/real-model/sources.json').read_text(encoding='utf-8'))
    source=ApiRepository(ROOT/'data/real-model/records',ContractGate())
    chunks=source.paper(source_ids['attention_id'])['chunks'][:10]
    reranker=qa_retriever(source).reranker
    started=time.perf_counter()
    worker=resident_worker(reranker.python,reranker.path)
    startup=worker.prepare(timeout=90)
    startup['parent_wait_seconds']=time.perf_counter()-started
    result={'scope':'官方 pdf/ 真文件Attention v7前10块，与live.json冷/温基准输入一致；非RRF实际top10质量测试。',
        'purpose':'只量完整推理耗时；90秒诊断时限不进入HTTP，生产仍严格5秒、超过预算保留RRF。',
        'question':'Which optimizer?', 'chunk_ids':[c['chunk_id'] for c in chunks], 'startup':startup,'samples':[]}
    for i in range(2):
        started=time.perf_counter()
        output,info=worker.score({'question':result['question'], 'items':[
            {'id':c['chunk_id'],'text':c['text'][:2000]} for c in chunks]},budget=90)
        elapsed=time.perf_counter()-started
        result['samples'].append({'sample':i+1,'elapsed_seconds':elapsed, 'timing':output['timing'],
            'model':output['model'],'revision':output['revision'], 'score_count':len(output['scores']),
            'scores_valid':set(output['scores'])=={c['chunk_id'] for c in chunks},
            'fits_production_budget':elapsed<=5,**info})
    close_workers()
    result['worker_source_sha256_lf']=hashlib.sha256((ROOT/'backend/scholar_graph/vector_worker.py').read_text(encoding='utf-8').encode()).hexdigest()
    raw=json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False)
    key=os.environ.get('DEEPSEEK_API_KEY')
    if key and key in raw:
        raise RuntimeError('Credential safety check rejected report')
    (ROOT/'tests/reports/reranker-top10-benchmark.json').write_text(raw+'\n',encoding='utf-8')
    print(json.dumps({'startup':startup,'samples':result['samples']},ensure_ascii=False),flush=True)


if __name__=='__main__':
    main()

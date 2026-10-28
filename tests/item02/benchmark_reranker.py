"""Real warm full top-ten CPU timing on identical RRF candidates; no production budget override."""
import contextlib
import hashlib
import json
import math
from pathlib import Path
import sys
import time

ROOT=Path(__file__).resolve().parents[2]; sys.path.insert(0,str(ROOT/'backend/scholar_graph'))
import vector_worker

def main():
    import torch
    base=ROOT/'data/item02-20261028'; payload=json.loads((base/'rerank-pool.json').read_text(encoding='utf-8'))
    result={'method':'real_bge_reranker_large_cpu_identical_top10','budget_seconds':5,'samples':[]}
    started=time.perf_counter()
    with contextlib.redirect_stdout(sys.stderr): loaded=vector_worker.load_reranker(str(ROOT/'data/module-four-models/bge-reranker-large'))
    result['load_seconds']=round(time.perf_counter()-started,6)
    baseline=None
    for threads in [2,4,8,2]:
        torch.set_num_threads(threads)
        for iteration in range(2):
            started=time.perf_counter()
            with contextlib.redirect_stdout(sys.stderr): output=vector_worker.rerank(payload,loaded)
            elapsed=time.perf_counter()-started; scores=output['scores']
            assert len(scores)==10 and all(math.isfinite(x) for x in scores.values())
            order=sorted(scores,key=lambda k:(-scores[k],k))
            if baseline is None: baseline=scores
            row={'threads':threads,'iteration':iteration+1,'seconds':round(elapsed,6),'fits_five_seconds':elapsed<=5,
                 'order':order,'same_order_as_baseline':order==sorted(baseline,key=lambda k:(-baseline[k],k)),
                 'max_score_difference':max(abs(scores[k]-baseline[k]) for k in scores)}
            result['samples'].append(row)
            (base/'rerank-thread-benchmark.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
            print(json.dumps({k:v for k,v in row.items() if k!='order'}),flush=True)
    result['input_chunk_ids']=[x['id'] for x in payload['items']]
    result['worker_sha256']=hashlib.sha256((ROOT/'backend/scholar_graph/vector_worker.py').read_bytes()).hexdigest()
    (base/'rerank-thread-benchmark.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')

if __name__=='__main__': main()

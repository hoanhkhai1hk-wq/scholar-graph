"""Actual BGE-M3/RRF top ten from the current official Attention parse."""
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[2]; sys.path.insert(0,str(ROOT/'backend'))
from scholar_graph.api_repository import ApiRepository
from scholar_graph.validation import ContractGate
from scholar_graph.vector_search import BgeChromaSearch
from scholar_graph.qa_retrieval import QAHybridRetriever

if __name__=='__main__':
    base=ROOT/'data/item02-20261028'; pid='paper-bdfaa68d8984f0dc02beaca527b76f207d99b666d31d1da728ee0728182df697'
    repo=ApiRepository(base/'records',ContractGate()); bundle=repo.paper(pid)
    vector=BgeChromaSearch(ROOT/'data/module-four-runtime/.venv/Scripts/python.exe',ROOT/'data/module-four-models/bge-m3',base/'rerank-index',timeout=600)
    question='其中Adam优化器的超参数β₁和β₂分别被设置为了多少？'
    evidence,meta=QAHybridRetriever(repo,vector).retrieve(bundle,question)
    assert meta['method']=='hybrid' and meta['ranking_method']=='rrf'
    ids=list(dict.fromkeys(e['anchor']['chunk_id'] for e in evidence))[:10]; assert len(ids)==10
    chunks={c['chunk_id']:c for c in bundle['chunks']}
    value={'question':question,'items':[{'id':cid,'text':chunks[cid]['text'][:2000]} for cid in ids],'retrieval':meta}
    with (base/'rerank-pool.json').open('x',encoding='utf-8') as f: json.dump(value,f,ensure_ascii=False,indent=2)
    print(json.dumps({'method':meta['method'],'candidate_count':len(ids),'retrieval_seconds':meta['elapsed_seconds']},ensure_ascii=False),flush=True)

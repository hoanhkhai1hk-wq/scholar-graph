"""Real optional host BGE+RRF+bounded rerank+DeepSeek integration, separate from no-BGE HTTP tests."""
import json
import os
from pathlib import Path
import sys
import time

ROOT=Path(__file__).resolve().parents[2]; sys.path.insert(0,str(ROOT/'backend'))
from scholar_graph.api_repository import ApiRepository
from scholar_graph.validation import ContractGate
from scholar_graph.vector_search import BgeChromaSearch
from scholar_graph.qa_retrieval import QAHybridRetriever,LocalReranker
from scholar_graph.grounded_model import GroundedModelAnswerer
from scholar_graph.deepseek_client import DeepSeekClient
from scholar_graph.rerank_worker import resident_worker,close_workers

if __name__=='__main__':
    from local_environment import configured_environment
    configured=configured_environment()
    for name in ['DEEPSEEK_API_KEY','DEEPSEEK_MODEL']:
        if configured.get(name): os.environ[name]=configured[name]
    base=ROOT/'data/item02-20261028'; repo=ApiRepository(base/'records',ContractGate())
    python=ROOT/'data/module-four-runtime/.venv/Scripts/python.exe'; model=ROOT/'data/module-four-models/bge-reranker-large'
    reranker=LocalReranker(base,python,model,resident=True)
    report={'mode':'real_host_bge_rrf_rerank_deepseek','cases':[],'warm_preparation':resident_worker(python,model).prepare(timeout=90)}
    try:
        for question in ['其中Adam优化器的超参数β₁和β₂分别被设置为了多少？','Transformer的Base模型训练用了多少个GPU？具体型号是什么？']:
            vector=BgeChromaSearch(python,ROOT/'data/module-four-models/bge-m3',base/'rerank-index',timeout=600)
            retrieval=QAHybridRetriever(repo,vector,reranker); client=DeepSeekClient.environment(); started=time.perf_counter()
            value,evidence=GroundedModelAnswerer(repo.gate,client,retriever=retrieval).answer(repo.paper('paper-bdfaa68d8984f0dc02beaca527b76f207d99b666d31d1da728ee0728182df697'),question)
            row={'question':question,'seconds':round(time.perf_counter()-started,6),'result':value,'retrieval':retrieval.metadata(),'model_calls':client.calls}
            report['cases'].append(row)
            (base/'hybrid-live.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
            print(json.dumps({'seconds':row['seconds'],'refused':value['refused'],'ranking':row['retrieval']['ranking_method'],'retrieval':row['retrieval']['retrieval']},ensure_ascii=False),flush=True)
    finally: close_workers()

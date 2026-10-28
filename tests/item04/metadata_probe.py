"""Fresh real title download after metadata fix, no overwrite of previous evidence."""
import argparse
import json
import os
import sys
import time
from common import ROOT,BASE,write
sys.path.insert(0,str(ROOT/'backend'))
from scholar_graph.api_repository import ApiRepository
from scholar_graph.arxiv_fetch import ArxivFetcher
from scholar_graph.validation import ContractGate

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--run',required=True);args=parser.parse_args()
    out=BASE/args.run;out.mkdir(exist_ok=False)
    os.environ.update(SCHOLAR_GRAPH_DEDUP_MODE='off',SCHOLAR_GRAPH_GROBID_ENABLED='true',GROBID_URL='http://127.0.0.1:8070')
    fetcher=ArxivFetcher(ApiRepository(out/'records',ContractGate()))
    started=time.monotonic()
    result=fetcher.fetch(title='BERT: Pre-training of Deep Bidirectional Transformers for Language Understanding')
    value={'elapsed_seconds':round(time.monotonic()-started,3),'result':result}
    write(out/'result.json',value)
    assert result['succeeded'],result
    paper=result['paper'];assert paper['institutions']==['Google AI Language'],paper
    assert paper['authors']==['Jacob Devlin','Ming-Wei Chang','Kenton Lee','Kristina Toutanova']
    print(json.dumps({'passed':True,'seconds':value['elapsed_seconds'],'paper':paper},ensure_ascii=False))

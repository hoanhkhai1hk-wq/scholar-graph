"""Redownload the actual failed PDF and preserve its raw parser evidence."""
import collections
import argparse
import json
import sys
from common import ROOT,BASE,write,digest
sys.path.insert(0,str(ROOT/'backend'))
from scholar_graph.arxiv_fetch import ArxivClient
from scholar_graph.pipeline import Pipeline
from scholar_graph.normalize import normalize
from scholar_graph.reference_identity import bibliography_sources
from scholar_graph.validation import ContractGate

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--run',required=True);args=p.parse_args()
    task=json.loads((BASE/'batch-all/task.json').read_text(encoding='utf-8'))
    item=next(i for i in task['result']['items'] if i.get('metadata') and i['metadata']['arxiv_id'].startswith('1609.08144'))
    out=BASE/args.run;out.mkdir(exist_ok=False)
    c=ArxivClient(ContractGate());source=out/'source.pdf';source.write_bytes(c.pdf(item['metadata']))
    pipeline=Pipeline(out/'records');paper,ocr=Pipeline._inspect(source.read_bytes(),digest(source))
    native=pipeline.engines.text(source);write(out/'native.json',native)
    bundle=normalize(native,None,paper,ocr,include_references=False);write(out/'chunks.json',bundle['chunks'])
    entries=bibliography_sources(bundle['chunks']);write(out/'bibliography-sources.json',entries)
    counts=collections.Counter(e['number'] for e in entries)
    duplicate=[e for e in entries if counts[e['number']]>1]
    write(out/'duplicates.json',duplicate)
    print(json.dumps({'pdf_sha256':digest(source),'pages':paper['page_count'],'duplicates':duplicate},ensure_ascii=False))

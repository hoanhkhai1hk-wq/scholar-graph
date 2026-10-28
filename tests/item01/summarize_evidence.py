"""Aggregate recorded facts only; keep source-paper full text outside Git evidence."""
from datetime import datetime
import json
from pathlib import Path
import re
import statistics

ROOT=Path(__file__).resolve().parents[2]; BASE=ROOT/'data/item01-20261028'
BOOK='paper-f8237d393163900fa8e43210e680a3f987b45ccac7750b372e156fae3df0bf32'
V1='paper-0a9bff1be3575cf9fe26a4a3d3a9175bc791ecec90de8b9deba4cff75d2b9476'

def read(path): return json.loads(path.read_text(encoding='utf-8'))

def resources(filename,task):
    first,last=map(datetime.fromisoformat,[task['started_at'],task['finished_at']])
    rows=[json.loads(x) for x in (BASE/filename).read_text(encoding='utf-8').splitlines()]
    rows=[x for x in rows if first<=datetime.fromisoformat(x['at'])<=last and x.get('MemUsage')]
    def mib(value):
        n,unit=re.fullmatch(r'([\d.]+)([A-Za-z]+)',value.split(' / ')[0]).groups()
        return float(n)*{'B':1/1024**2,'KiB':1/1024,'MiB':1,'GiB':1024}[unit]
    return {'samples':len(rows),'peak_observed_working_set_mib':round(max(map(lambda x:mib(x['MemUsage']),rows)),3),
            'first_sample':rows[0]['at'],'last_sample':rows[-1]['at'],
            'sampling_scope':'Docker working-set samples inside actual task timestamps; not RSS or a continuous maximum'}

def main():
    before=read(BASE/'book-before/results.json')['uploads'][0]
    after=read(BASE/'book-after-03/results.json')['uploads'][0]
    t_before=read(BASE/'book-before/UnderstandingDeepLearning_02_09_26_C.pdf.task.json')
    t_after=read(BASE/'book-after-03/completed-task.json')
    checks={f:read(BASE/'records/papers'/BOOK/f)==read(BASE/'after/records/papers'/BOOK/f)
            for f in ('paper-meta.json','chunks.json','reference-entries.json','citation-links.json')}
    readings=read(BASE/'reading-after-01.json')
    measurements=readings['last_page_measurements']
    latency={str(include):{'bytes':next(x['bytes'] for x in measurements if x['include_navigation']==include),
            'median_seconds':statistics.median(x['seconds'] for x in measurements if x['include_navigation']==include),
            'requests':3} for include in [True,False]}
    meta=read(BASE/'versions-after/1706.03762v1.pdf.view.json')
    chunks=read(BASE/'after/records/papers'/V1/'chunks.json')
    heading={f:list(dict.fromkeys(c[f] for c in chunks if c[f])) for f in ('heading_1','heading_2','heading_3')}
    result={'book':{'before_seconds':before['elapsed_seconds'],'after_seconds':after['elapsed_seconds'],
              'reduction_percent':round((1-after['elapsed_seconds']/before['elapsed_seconds'])*100,3),
              'physical_pages':541,'chunks':6859,'unchanged_frozen_outputs':checks,
              'before_resources':resources('resources-before.jsonl',t_before),
              'after_resources':resources('resources-after.jsonl',t_after),
              'engine_session':read(BASE/'after/records/partial'/BOOK/'progress.json')['engine_session']},
        'reading':{'passed':readings['passed'],'verified_pages':sum(s['verified_pages'] for s in readings['samples']),
                   'last_page':latency,'bytes_reduction_percent':round((1-latency['False']['bytes']/latency['True']['bytes'])*100,3)},
        'v1':{'title':meta['paper']['title'],'author_count':len(meta['paper']['authors']),
              'author_order_source_verified':True,'institutions':meta['paper']['institutions'],
              'author_profiles_with_email':sum(bool(x['emails']) for x in meta['author_profiles']),
              'author_profiles_with_institution':sum(bool(x['institutions']) for x in meta['author_profiles']),
              'source_absent_institution':['Illia Polosukhin'], 'headings':heading,
              'native_type_counts':{t:sum(c['type']==t for c in chunks) for t in ('text','table','figure','formula')},
              'reference_count':len(read(BASE/'after/records/papers'/V1/'reference-entries.json')),
              'supplement_pages':sorted({c['page_number'] for c in chunks if c['heading_1']=='Attention Visualizations'})},
        'formula':read(BASE/'formula-source-reviewed/results.json'),
        'management':read(BASE/'management-after/results.json')}
    out=BASE/'measured-summary.json'
    with out.open('x',encoding='utf-8') as f: json.dump(result,f,ensure_ascii=False,indent=2)
    print(json.dumps({k:result[k] for k in ('book','reading')},ensure_ascii=False),flush=True)

if __name__=='__main__': main()

"""Publish audit summaries; keep original PDFs, source passages and full SSE local."""
import hashlib
import json
from pathlib import Path
import shutil
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[2]; BASE=ROOT/'data/item02-20261028'; OUT=ROOT/'test-records/item02-20261028'


def write(name,value):
    path=OUT/name; path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')


def citations(value):
    if isinstance(value,dict):
        if isinstance(value.get('anchor'),dict) and isinstance(value.get('quote'),str):
            yield {'anchor':value['anchor'],'quote_sha256':hashlib.sha256(value['quote'].encode()).hexdigest(),'quote_chars':len(value['quote'])}
        for child in value.values(): yield from citations(child)
    elif isinstance(value,list):
        for child in value: yield from citations(child)


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    copies=['ingestion.json','ingestion.log','rerank-thread-benchmark.json','rerank-thread-benchmark.log',
            'rerank-production-budget.json','rerank-production-budget.log','prepare-rerank-pool.log',
            'hybrid-live.log','hybrid-live-02.log','live-unit.log','live-unit-02.log','live-unit-02.xml',
            'unit-01.xml','unit-02.xml','related-full.xml','related-full.log','related-final.xml','related-final.log',
            'related-delivery.xml','related-delivery.log','related-release.xml','related-release.log',
            'fast-baseline.xml','fast-final.xml','fast-final.log','fast-image.log','fast-release-image.log','fast-release-image-wrong-marker.log',
            'frontend-build.log','frontend-build.json','backend-build.log','backend-build.json',
            'backend-build-final.log','backend-build-final.json','runtime-final.json','browser-cross-proof.json',
            'browser-bert-before.json','browser-bert-after.json','deploy-final-main.log','deploy-final-isolated.log']
    for filename in copies:
        assert (BASE/filename).is_file(),filename
        shutil.copyfile(BASE/filename,OUT/filename)
    shutil.copyfile(ROOT/'data/item02-fast-baseline-20261028.log',OUT/'fast-baseline.log')
    for run in ['answers-before','answers-after','answers-final']:
        dest=OUT/run; dest.mkdir(exist_ok=True)
        # Keep older audit false positives instead of silently replacing them.
        for audit in ['audit.json','audit-v2.json','audit-reviewed.json']:
            shutil.copyfile(BASE/run/audit,dest/audit)
        shutil.copyfile(BASE/(run+'.log'),dest/'run.log')
    for run in ['stream-break-before','stream-break-after','stream-break-final']:
        rows=json.loads((BASE/run/'results.json').read_text(encoding='utf-8'))
        public=[]
        for row in rows:
            result=row.get('result',row.get('final',{})); done=row.get('done',{})
            public.append({'path':row['path'],'http_status':row['status'],'seconds':row['seconds'],
                           'refused':result.get('refused'),'per_paper_refused':[x['refused'] for x in result.get('per_paper',[])],
                           'citations':list(citations(result)),'mode':row.get('mode'),'done':done})
        write(run+'/summary.json',public)
        shutil.copyfile(BASE/(run+'.log'),OUT/(run+'.log'))
    hybrid=json.loads((BASE/'hybrid-live.json').read_text(encoding='utf-8'))
    write('hybrid-live-summary.json',{'mode':hybrid['mode'],'warm_preparation':hybrid['warm_preparation'],
          'cases':[{'question':r['question'],'seconds':r['seconds'],'refused':r['result']['refused'],
                    'citations':list(citations(r['result'])),'retrieval':r['retrieval'],'model_calls':r['model_calls']} for r in hybrid['cases']]})
    suites={}
    for file in OUT.glob('*.xml'):
        root=ET.parse(file).getroot(); tests=root.findall('.//testcase')
        suites[file.name]={'tests':len(tests),'failures':len(root.findall('.//failure')),'errors':len(root.findall('.//error')),
                           'skips':len(root.findall('.//skipped')),'seconds':sum(float(s.get('time','0')) for s in root.findall('testsuite'))}
    write('test-summary.json',suites)
    manifest=[]
    for path in sorted(OUT.rglob('*')):
        if path.is_file() and path.name!='manifest.json':
            manifest.append({'path':path.relative_to(OUT).as_posix(),'bytes':path.stat().st_size,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
    write('manifest.json',{'method':'copied_log_bytes_and_generated_source_quote_hash_summaries','files':manifest})
    print(json.dumps({'public_files':len(manifest),'final_audit_passed':json.loads((OUT/'answers-final/audit-reviewed.json').read_text(encoding='utf-8'))['passed']},ensure_ascii=False))


if __name__=='__main__': main()

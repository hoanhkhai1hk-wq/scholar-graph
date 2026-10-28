"""Append repeat evidence without changing the initial run's frozen artifacts."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import xml.etree.ElementTree as ET
from curate_evidence import citations

ROOT=Path(__file__).resolve().parents[2]; BASE=ROOT/'data/item02-20261028'; OUT=ROOT/'test-records/item02-20261028'


def write(path,value):
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')


def main():
    parser=argparse.ArgumentParser(); parser.add_argument('--label',required=True); parser.add_argument('--run',required=True); parser.add_argument('--probe',required=True); args=parser.parse_args()
    destination=OUT/args.label; destination.mkdir(exist_ok=False)
    run=BASE/args.run
    for source,name in [('audit.json','audit-initial.json'),('audit-source-reviewed.json','audit-source-reviewed.json'),
                        ('source-review.json','source-review.json'),('audit-without-source-review.json','audit-without-source-review.json')]:
        shutil.copyfile(run/source,destination/name)
    for name in [args.run+'.log','repeat-fast.log','repeat-fast.xml','repeat-fast-final.log','repeat-fast-final.xml',
                 'related-repeat-20261028-01.log','related-repeat-20261028-01.xml',args.probe+'.log',
                 'repeat-audit-negative.json','repeat-audit-without-review.log','runtime-final.json',
                 'user-followup-browser-smoke.json','user-followup-anchor-smoke.json','user-followup-restore-smoke.json']:
        shutil.copyfile(BASE/name,destination/name)
    rows=json.loads((BASE/args.probe/'results.json').read_text(encoding='utf-8'))
    public=[]
    for row in rows:
        result=row.get('result',row.get('final',{}))
        public.append({'path':row['path'],'http_status':row['status'],'seconds':row['seconds'],'refused':result.get('refused'),
                       'per_paper_refused':[x['refused'] for x in result.get('per_paper',[])],
                       'citations':list(citations(result)),'mode':row.get('mode'),'done':row.get('done')})
    write(destination/'compare-summary.json',public)
    summary=json.loads((OUT/'test-summary.json').read_text(encoding='utf-8'))
    for path in destination.glob('*.xml'):
        root=ET.parse(path).getroot()
        summary[path.relative_to(OUT).as_posix()]={'tests':len(root.findall('.//testcase')),'failures':len(root.findall('.//failure')),
            'errors':len(root.findall('.//error')),'skips':len(root.findall('.//skipped')),
            'seconds':sum(float(s.get('time','0')) for s in root.findall('testsuite'))}
    write(OUT/'test-summary.json',summary)
    manifest=[]
    for path in sorted(OUT.rglob('*')):
        if path.is_file() and path.name!='manifest.json':
            manifest.append({'path':path.relative_to(OUT).as_posix(),'bytes':path.stat().st_size,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
    write(OUT/'manifest.json',{'method':'copied_log_bytes_and_generated_source_quote_hash_summaries','files':manifest})
    audit=json.loads((destination/'audit-source-reviewed.json').read_text(encoding='utf-8'))
    assert audit['passed'] and len(audit['cases'])==14
    print(json.dumps({'new_evidence_files':len(list(destination.iterdir())),'manifest_files':len(manifest),'source_reviewed_cases':len(audit['cases'])}))


if __name__=='__main__': main()

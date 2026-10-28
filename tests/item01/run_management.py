"""Real metadata, deletion/restoration, version choice and batch upload acceptance."""
import argparse
import hashlib
import json
from pathlib import Path
import time

import httpx

ROOT = Path(__file__).resolve().parents[2]
V7 = 'paper-bdfaa68d8984f0dc02beaca527b76f207d99b666d31d1da728ee0728182df697'
V1 = 'paper-0a9bff1be3575cf9fe26a4a3d3a9175bc791ecec90de8b9deba4cff75d2b9476'


def main():
    parser=argparse.ArgumentParser(); parser.add_argument('--run',required=True)
    parser.add_argument('--records',type=Path,default=ROOT/'data/item01-20261028/records')
    parser.add_argument('--base',default='http://127.0.0.1:8040')
    args=parser.parse_args()
    out=(ROOT/'data/item01-20261028'/args.run).resolve()
    if not out.is_relative_to(ROOT/'data/item01-20261028'): raise ValueError('Invalid evidence path')
    out.mkdir(parents=True,exist_ok=False)
    report={'passed':False,'checks':{}}
    def save(): (out/'results.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    def frozen(): return {str(p.relative_to(args.records)):hashlib.sha256(p.read_bytes()).hexdigest()
        for name in ('papers','comparisons','original-pdfs') for p in (args.records/name).rglob('*') if p.is_file()}
    save()
    try:
        with httpx.Client(base_url=args.base,trust_env=False,timeout=60) as client:
            def req(method,path,**kw):
                r=client.request(method,path,**kw); r.raise_for_status(); return r.json()
            initial=frozen()
            if not initial: raise ValueError('No actual frozen input records to protect')
            before=req('GET','/api/v2/papers/'+V1)
            original=before['paper']['title']
            req('PATCH','/api/v2/papers/'+V1,json={'title':original+'（验收临时修正）'})
            report['checks']['metadata_update_visible']=req('GET','/api/v2/papers/'+V1)['paper']['title'].endswith('（验收临时修正）')
            req('PATCH','/api/v2/papers/'+V1,json={'title':original})
            report['checks']['metadata_restored']=req('GET','/api/v2/papers/'+V1)['paper']['title']==original
            req('DELETE','/api/v2/papers/'+V1)
            report['checks']['deleted_from_library']=V1 not in {r['paper']['id'] for r in req('GET','/api/v2/papers')['items']}
            report['checks']['visible_in_recycle_bin']=V1 in {r['paper']['id'] for r in req('GET','/api/v2/papers?archived=true')['items']}
            req('POST','/api/v2/papers/'+V1+'/restore')
            report['checks']['restored_to_library']=V1 in {r['paper']['id'] for r in req('GET','/api/v2/papers')['items']}
            report['choices']=[]
            for choice,expected in [('keep_old',{V7}),('keep_new',{V1}),('keep_both',{V7,V1})]:
                req('POST','/api/v2/papers/'+V1+'/version-choice',json={'choice':choice})
                visible={r['paper']['id'] for r in req('GET','/api/v2/papers')['items']} & {V7,V1}
                row={'choice':choice,'visible':sorted(visible),'passed':visible==expected}
                report['choices'].append(row)
            report['checks']['all_three_version_choices']=all(r['passed'] for r in report['choices'])
            report['checks']['frozen_files_unchanged_after_management']=initial==frozen()
            report['frozen_file_count']=len(initial); save()
            sources=[ROOT/'pdf/1607.06450v1.pdf',ROOT/'pdf/N19-1423.pdf']
            opened=[p.open('rb') for p in sources]
            try:
                started=time.monotonic()
                task=req('POST','/api/v2/uploads',files=[('files',(p.name,f,'application/pdf')) for p,f in zip(sources,opened,strict=True)])
            finally:
                for f in opened: f.close()
            while task['status'] in ('queued','running','cancelling'):
                if time.monotonic()-started>600: raise TimeoutError('Batch did not finish')
                time.sleep(.5); task=req('GET','/api/v2/tasks/'+task['id'])
            (out/'batch-task.json').write_text(json.dumps(task,ensure_ascii=False,indent=2),encoding='utf-8')
            report['batch_elapsed_seconds']=round(time.monotonic()-started,3)
            report['checks']['two_official_files_batch_completed']=task['status']=='completed' and len(task['result']['succeeded'])==2 and not task['result']['failed']
            report['batch_papers']=[req('GET','/api/v2/papers/'+row['paper_id'])['paper'] for row in task['result']['succeeded']]
            report['passed']=all(report['checks'].values())
    except Exception as error: report['error']={'type':type(error).__name__,'message':str(error)}
    finally: save()
    print(json.dumps(report,ensure_ascii=False),flush=True)
    return 0 if report['passed'] else 1


if __name__=='__main__': raise SystemExit(main())

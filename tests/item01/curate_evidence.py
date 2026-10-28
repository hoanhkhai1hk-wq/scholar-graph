"""Publish measurements and command output, leaving full paper contents in local data/."""
import json
from pathlib import Path
import shutil

ROOT=Path(__file__).resolve().parents[2]
BASE=ROOT/'data/item01-20261028'; OUT=ROOT/'test-records/item01-20261028'

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    files=['quality-unit-02.xml','formula-unit-01.xml','fast-local-final.xml','related-full-01/junit.xml',
           'related-candidate-01.xml','snapshot-fast.xml','snapshot-related.xml','snapshot-proxy.xml',
           'fast-local-final.log','fast-candidate-01.log','related-full-01.log','related-candidate-01.log',
           'snapshot-fast.log','snapshot-related.log','snapshot-proxy.log',
           'browser-01.log','browser-02.log','reading-after-01.json',
           'page-audit-before-02.json','page-audit-after.json','resources-before.jsonl','resources-after.jsonl',
           'backend-build-final.log','backend-build-final.json','frontend-build-final.log',
           'snapshot-frontend-build.log','snapshot-frontend-build-03.log',
           'formula-download-02/result.json','structure-after-01/results.json','structure-after-02/results.json',
           'formula-source-reviewed/results.json','book-after-03/completed-task.json',
           'management-before/restart.json','fast-image-final.xml','related-image-final.xml',
           'runtime-main-final.json','delivery-check-final.json','snapshot-frontend-final.log']
    files += [name+'/results.json' for name in ['versions-before','versions-after','scan-before','scan-after',
                                               'book-before','book-after','book-after-02','book-after-03']]
    files += [p.name for p in BASE.glob('*final*.log')]
    for name in sorted(set(files)):
        source=BASE/name
        if not source.is_file(): continue
        destination=OUT/name; destination.parent.mkdir(parents=True,exist_ok=True); shutil.copyfile(source,destination)
    for name in ['management-before','management-after','measured-summary.json']:
        source=BASE/(name if name.endswith('.json') else name+'/results.json')
        d=json.loads(source.read_text(encoding='utf-8'))
        management=d.get('management',d)
        if 'batch_papers' in management:
            management['batch_papers']=[{k:p[k] for k in ['id','file_hash','page_count']} for p in management['batch_papers']]
        target=OUT/(name if name.endswith('.json') else name+'/results.json'); target.parent.mkdir(parents=True,exist_ok=True)
        target.write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding='utf-8')
    browser=ROOT/'data/workbench-runtime/browser-runs/item01-browser-02'
    if (browser/'browser-results.json').is_file(): shutil.copyfile(browser/'browser-results.json',OUT/'browser-results.json')
    for image in (browser/'browser-artifacts').rglob('*.png'):
        # Screenshots explicitly requested; omit traces and embedded source PDFs.
        shutil.copyfile(image,OUT/'screenshots'/image.name)
    print(json.dumps({'evidence_files':sum(p.is_file() for p in OUT.rglob('*')),
                       'pdf_files':sum(p.suffix.lower()=='.pdf' for p in OUT.rglob('*'))}))

if __name__=='__main__': main()

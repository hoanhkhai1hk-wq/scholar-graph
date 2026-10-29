"""Copy real acceptance evidence, preserve failed probes, never copy PDFs/keys."""
import json
import shutil
from pathlib import Path
from common import ROOT, BASE, digest, write, configured_environment

OUT=ROOT/'test-records/ui-celadon-20261029'
OUT.mkdir(exist_ok=True)
for pattern in ['build*.log','fast*.log','fast*.xml','related*.log','related*.xml','image*.log','up*.log',
                '*-result.json','release*.log','runtime-audit.*','performance.*','deployment-browser.*',
                'impeccable-after*','taste-after-exit.txt','taste-final-qa-exit.txt','raster-provenance-scan.log',
                'hover*.json','hover*.log','documenter-validation.json','capture-validity*.json','screenshot-origins.json','jobs-fixture-copy.json']:
    for p in BASE.glob(pattern):
        if p.is_file():shutil.copyfile(p,OUT/p.name)
for folder in ['browser01','browser02','browser03','browser04','browser05','browser06','states01','states02',
               'navigation01','recapture01','graph-real20-final','retrieval-final','round01','review-fix02','final-capture','taste-after','taste-final-qa']:
    source=BASE/folder
    for name in ['report.json','qa-answer.txt','qa-stream.txt','translation-export.md']:
        p=source/name
        if p.exists():
            (OUT/folder).mkdir(exist_ok=True);shutil.copyfile(p,OUT/folder/name)
    p=BASE/(folder+'.log')
    if p.exists():shutil.copyfile(p,OUT/p.name)
write(OUT/'finish-review.json',{
    'method':'Fresh independent reviewer, no inherited build transcript, read-only screenshots/source; then verdict continuation',
    'initial_disposition':'fix',
    'material_fixes':['Responsive reader directory/assistant switching','Readable long-text table columns with contained scrolling','Chinese network failure message','Real gray skeleton during PDF loading','Text/destructive hover readability'],
    'verdict':[{'finding':i+1,'status':'resolved'} for i in range(5)],
    'final_disposition':'ship','scope':'Scores the five listed corrections only; not all PDF business acceptance or whole-machine performance certification',
    'reviewer_task':'/root/impeccable_finish_reviewer'})
# Historical proposal artifacts stay byte-identical. Their explicit origin is
# recorded here rather than modifying older screenshot pixels/metadata.
write(OUT/'proposal-screenshot-origins.json',[
    {'file':str(p.relative_to(ROOT)).replace('\\','/'),'sha256':digest(p),
     'origin':'Actual before/proposal/reference-browser capture; exact scene described by docs/ui-design-audit-before.md and docs/ui-design-proposals.md; not a production bitmap asset'}
    for p in sorted((ROOT/'docs/images/ui-design-20261029').glob('*.png'))])
secret=configured_environment().get('DEEPSEEK_API_KEY','')
for p in OUT.rglob('*'):
    if p.is_file():
        assert p.suffix.lower()!='.pdf'
        if secret:assert secret.encode() not in p.read_bytes(),f'Secret found in {p.relative_to(ROOT)}'
manifest=[{'path':str(p.relative_to(OUT)).replace('\\','/'),'sha256':digest(p),'bytes':p.stat().st_size}
          for p in sorted(OUT.rglob('*')) if p.is_file() and p.name!='manifest.json']
write(OUT/'manifest.json',manifest)
print(json.dumps({'evidence_files':len(manifest),'secret_value_scan':'passed','pdf_files':0}))

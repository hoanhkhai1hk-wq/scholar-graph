"""Public provenance summaries; original PDFs/full official translations remain local."""
import hashlib,json,shutil
from pathlib import Path
import xml.etree.ElementTree as ET
ROOT=Path(__file__).resolve().parents[2];BASE=ROOT/'data/item03-20261028';OUT=ROOT/'test-records/item03-20261028'
def read(path):return json.loads(path.read_text(encoding='utf-8-sig'))
def write(path,value):path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def digest(text):return hashlib.sha256(text.encode('utf-8')).hexdigest()
if __name__=='__main__':
    OUT.mkdir(exist_ok=True)
    copies=['ingestion.json','ingestion.log','fast-baseline.xml','fast-baseline.log','fast-final.xml','fast-final.log',
            'related-01.xml','related-final.xml','related-final.log','related-release.xml','related-release.log','related-complete.xml','related-complete.log',
            'frontend-build.json','frontend-build.log','backend-build.json','backend-build.log','backend-build-final.json','backend-build-final.log',
            'frontend-build-final.json','frontend-build-final.log','backend-build-abstract-fix.json','backend-build-abstract-fix.log',
            'backend-build-release.json','backend-build-release.log','frontend-build-release.log','deploy-main.log','deploy-release.log',
            'title-tree-before.json','title-tree-after.json','citation-inbound-before.json','citation-inbound-after.json',
            'citation-reference-before.json','citation-reference-after.json','citation-return-before.json','citation-return-before-hit.json','citation-return-after.json',
            'citation11-reference-after.json','citation11-return-after.json','hover-after.json','selection-after.json','sync-drag-before.json',
            'sync-left-after-wheel.json','sync-right-after-wheel.json','sync-left-after-drag-final.json','sync-right-after-drag-final.json',
            'sync-measurement.json','protection-fixtures.json','protection-fixture.log','protection-before.log','protection-after.log',
            'runtime-final.json','error-contracts.json','error-contracts.log','native-scroll-browser.log','native-scroll-release.log','native-final-release.log',
            'native-scroll-test-assumption-failure.json']
    for name in copies:assert (BASE/name).is_file(),name;shutil.copyfile(BASE/name,OUT/name)
    for run in ['translations-before','translations-after','translations-final']:
        raw=read(BASE/run/'results.json');summary={'run':run,'passed':raw['passed'],'cases':[]}
        for row in raw['cases']:
            name=row['case'];filename={'full_zh':'full-zh-response.json','full_en':'full-en-response.json'}.get(name,name+'-response.json')
            value=read(BASE/run/filename);metadata=value['metadata']
            summary['cases'].append({**row,'model_calls':metadata['model_calls'],'segments_manifest':[
                {'id':s['source_chunk_id'],'page':s['page_number'],'type':s['type'],'source_sha256':digest(s['source_text']),'translation_sha256':digest(s['translated_text'])} for s in value['segments']],
                'markdown_chars':len(value['markdown'] or ''),'markdown_sha256':digest(value['markdown']) if value['markdown'] else None,
                'translated_sample':next((s['translated_text'][:220] for s in value['segments'] if len(s['source_text'])>300),None)})
        write(OUT/run/'summary.json',summary);shutil.copyfile(BASE/(run+'.log'),OUT/(run+'.log'))
    for run in ['protection-before','protection-after']:
        write(OUT/run/'results.json',read(BASE/run/'results.json'))
        for path in (BASE/run).glob('*.json'):
            if path.name=='results.json':continue
            # These are small, self-authored control samples, not official corpus excerpts.
            write(OUT/run/path.name,read(path))
    for run in ['wrong-source-before','wrong-source-after']:
        write(OUT/run/'results.json',read(BASE/run/'results.json'));shutil.copyfile(BASE/(run+'.log'),OUT/(run+'.log'))
    write(OUT/'native-final-release/results.json',read(BASE/'native-final-release/native-scroll-result.json'))
    summary={}
    for path in OUT.glob('*.xml'):
        tree=ET.parse(path).getroot();summary[path.name]={'tests':len(tree.findall('.//testcase')),'failures':len(tree.findall('.//failure')),'errors':len(tree.findall('.//error')),'skips':len(tree.findall('.//skipped')),'seconds':sum(float(s.get('time','0')) for s in tree.findall('testsuite'))}
    write(OUT/'test-summary.json',summary)
    manifest=[]
    for path in sorted(OUT.rglob('*')):
        if path.is_file() and path.name!='manifest.json':manifest.append({'path':path.relative_to(OUT).as_posix(),'bytes':path.stat().st_size,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
    write(OUT/'manifest.json',{'method':'raw command bytes plus source/translation hash manifests','files':manifest})
    print(json.dumps({'public_files':len(manifest),'final_translation_cases':len(read(BASE/'translations-final/results.json')['cases']),'native_browser_passed':read(BASE/'native-final-release/native-scroll-result.json')['passed']}))

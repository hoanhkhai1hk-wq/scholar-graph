"""Allowlisted release checks; never inspect container credentials."""
import hashlib,json,subprocess,sys
from pathlib import Path
import httpx
ROOT=Path(__file__).resolve().parents[2];BASE=ROOT/'data/item03-20261028';sys.path.insert(0,str(ROOT/'backend'))
from scholar_graph.api_repository import ApiRepository
from scholar_graph.validation import ContractGate
from scholar_graph.workspace import Workspace

def command(*args):return subprocess.check_output(list(args),cwd=ROOT,text=True,encoding='utf-8').strip()
if __name__=='__main__':
    report={'systems':{},'source_hashes':{},'selection_calls':[]}
    with httpx.Client(trust_env=False,timeout=40) as c:
        for name,backend,frontend,count in [('main',8000,3000,0),('item03',8080,3380,3)]:
            s=c.get(f'http://127.0.0.1:{backend}/api/v2/system');s.raise_for_status();s=s.json()
            total=c.get(f'http://127.0.0.1:{backend}/api/v1/papers').json()['total'];assert total==count and s['model_configured'] and s['qa_mode']=='deepseek'
            page=c.get(f'http://127.0.0.1:{frontend}/');assert page.status_code==200
            project='scholar-graph' if name=='main' else 'scholar-graph-item03'
            dns=command('docker','exec',project+'-frontend-1','getent','hosts','backend');assert dns.startswith('172.')
            report['systems'][name]={'model_configured':True,'qa_mode':s['qa_mode'],'papers':total,'frontend_status':page.status_code,'backend_dns':dns}
            for service in ['backend','frontend']:
                state=json.loads(command('docker','inspect','--format','{{json .State}}',project+'-'+service+'-1'))
                health=state.get('Health',{}).get('Status','not_configured');assert state['Running'] and (health=='healthy' or name=='item03' and service=='frontend' and health=='not_configured')
                report['systems'][name][service]={'running':True,'health':health,'image_config_id':command('docker','inspect','--format','{{.Image}}',project+'-'+service+'-1')}
    files=['backend/scholar_graph/translation.py','backend/scholar_graph/workspace_translation.py','frontend/components/LayoutViewer.tsx',
           'frontend/components/BilingualPane.tsx','frontend/components/TranslatePanel.tsx','frontend/lib/bilingual-scroll.ts','frontend/app/globals.css']
    for path in files:
        expected=hashlib.sha256((ROOT/path).read_bytes()).hexdigest();service='backend' if path.startswith('backend') else 'frontend'
        for project in ['scholar-graph','scholar-graph-item03']:
            assert command('docker','exec',project+'-'+service+'-1','sha256sum','/app/'+path).split()[0]==expected,(project,path)
        report['source_hashes'][path]=expected
    workspace=Workspace(ApiRepository(BASE/'records',ContractGate()))
    for item in workspace.all('selection_translation'):
        t=item['translation'];report['selection_calls'].append({'selection':item['selection'],'model_calls':t['metadata']['model_calls'],
            'segments':[{'source_chunk_id':s['source_chunk_id'],'page_number':s['page_number'],'source_sha256':hashlib.sha256(s['source_text'].encode()).hexdigest(),'translated_text':s['translated_text']} for s in t['segments']]})
    official=ROOT/'pdf/1706.03762v7.pdf';ingestion=json.loads((BASE/'ingestion.json').read_text(encoding='utf-8'));assert hashlib.sha256(official.read_bytes()).hexdigest()==ingestion['sha256']
    original=json.loads((BASE/'translations-before/full-zh-response.json').read_text(encoding='utf-8'))
    exported=(BASE/'native-final-release/browser-export.md').read_bytes();assert exported==original['markdown'].encode('utf-8')
    report['export']={'bytes':len(exported),'sha256':hashlib.sha256(exported).hexdigest(),'matches_saved_full_translation':True}
    report['official_pdf_unchanged']=True;report['passed']=True
    (BASE/'runtime-final.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'passed':True,'systems':report['systems'],'matched_source_files':len(files),'selection_records':len(report['selection_calls']),'export_bytes':len(exported)},ensure_ascii=False))

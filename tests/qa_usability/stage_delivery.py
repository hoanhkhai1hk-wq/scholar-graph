"""Stage only this fix, preserving other work and original evidence bytes."""
import hashlib,json,subprocess,sys
from common import ROOT,BASE,write,digest
sys.path.insert(0,str(ROOT/'tests/item02'))
from local_environment import configured_environment

EXACT={'.gitattributes','backend/scholar_graph/workspace_query.py','backend/scholar_graph/workspace_overview.py',
    'backend/scholar_graph/workspace_research.py','frontend/components/ResearchChat.tsx','frontend/components/ReadingWorkbench.tsx',
    'tests/test_qa_usability.py','test-records/问答易用性修复报告.md'}
PREFIX=('tests/qa_usability/','test-records/qa-usability-20261028/')
def git(*args):return subprocess.check_output(['git',*args],cwd=ROOT)
def allowed(p):return p in EXACT or p.startswith(PREFIX)
if __name__=='__main__':
    assert not git('diff','--cached','--name-only','-z'),'Preexisting staged work must be kept separate'
    before=json.loads((BASE/'workspace-before.json').read_text(encoding='utf8'))
    unchanged={p:sha for p,sha in before['files'].items() if not allowed(p)}
    assert all(digest(ROOT/p)==sha for p,sha in unchanged.items())
    out=ROOT/'test-records/qa-usability-20261028';assert not (out/'manifest.json').exists()
    files=[{'path':p.relative_to(out).as_posix(),'bytes':p.stat().st_size,'sha256':digest(p)} for p in sorted(out.rglob('*')) if p.is_file()]
    write(out/'manifest.json',{'files':files})
    subprocess.run(['git','add','--',*sorted(EXACT),'tests/qa_usability','test-records/qa-usability-20261028'],cwd=ROOT,check=True,capture_output=True)
    subprocess.run(['git','add','--renormalize','--','test-records/qa-usability-20261028'],cwd=ROOT,check=True,capture_output=True)
    paths=[p for p in git('diff','--cached','--name-only','-z').decode().split('\0') if p]
    key=configured_environment()['DEEPSEEK_API_KEY'].encode();assert key
    for p in paths:
        assert allowed(p) and not p.lower().endswith('.pdf') and not p.startswith('pdf/') and key not in git('show',':'+p),p
    for row in files:
        data=git('show',':test-records/qa-usability-20261028/'+row['path'])
        assert len(data)==row['bytes'] and hashlib.sha256(data).hexdigest()==row['sha256'],row['path']
    subprocess.run(['git','diff','--cached','--check'],cwd=ROOT,check=True)
    report={'staged_files':len(paths),'staged_pdfs':0,'credential_occurrences':0,'evidence_hashes_verified':len(files),
        'preexisting_unrelated_files_unchanged':len(unchanged)}
    write(BASE/'stage-check.json',report);print(json.dumps(report))

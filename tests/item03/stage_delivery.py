"""Only item-3 paths; preserve unrelated modifications and verify evidence bytes."""
import hashlib,json,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];BASE=ROOT/'data/item03-20261028'
sys.path.insert(0,str(ROOT/'tests/item02'))
from local_environment import configured_environment
EXACT={'.gitattributes','backend/scholar_graph/translation.py','backend/scholar_graph/workspace_translation.py',
       'frontend/README.md','frontend/app/globals.css','frontend/components/BilingualPane.tsx','frontend/components/LayoutViewer.tsx',
       'frontend/components/ReaderPane.tsx','frontend/components/TranslatePanel.tsx','frontend/lib/bilingual-scroll.ts',
       'tests/test_item03_navigation.py','test-records/第3项报告.md'}
PREFIX=('tests/item03/','test-records/item03-20261028/')
def git(*args):return subprocess.check_output(['git',*args],cwd=ROOT)
def allowed(path):return path in EXACT or path.startswith(PREFIX)
if __name__=='__main__':
    assert git('rev-parse','HEAD').decode().strip()=='e7cc25e4df4f05f697b289a9f478ea8e78457f6b'
    assert not git('diff','--cached','--name-only')
    names=git('ls-files','-m','-o','--exclude-standard','-z').decode('utf-8').split('\0')
    unchanged={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in names if p and not allowed(p) and (ROOT/p).is_file()}
    (BASE/'unrelated-before-commit.json').write_text(json.dumps(unchanged,ensure_ascii=False,indent=2),encoding='utf-8')
    subprocess.run(['git','add','--',*sorted(EXACT),'tests/item03','test-records/item03-20261028'],cwd=ROOT,check=True,capture_output=True)
    subprocess.run(['git','add','--renormalize','--','test-records/item03-20261028'],cwd=ROOT,check=True,capture_output=True)
    files=[p for p in git('diff','--cached','--name-only','-z').decode('utf-8').split('\0') if p]
    key=configured_environment()['DEEPSEEK_API_KEY'].encode();assert key
    for path in files:
        assert allowed(path) and not path.lower().endswith('.pdf') and not path.startswith('pdf/'),path
        assert key not in git('show',':'+path),path
    manifest=json.loads((ROOT/'test-records/item03-20261028/manifest.json').read_text(encoding='utf-8'))
    for item in manifest['files']:
        content=git('show',':test-records/item03-20261028/'+item['path'])
        assert len(content)==item['bytes'] and hashlib.sha256(content).hexdigest()==item['sha256'],item['path']
    subprocess.run(['git','diff','--cached','--check'],cwd=ROOT,check=True)
    value={'staged_files':len(files),'staged_pdf_count':0,'configured_key_occurrences':0,'manifest_entries_match':len(manifest['files']),'unrelated_files_snapshotted':len(unchanged)}
    (BASE/'stage-check.json').write_text(json.dumps(value,indent=2),encoding='utf-8');print(json.dumps(value))

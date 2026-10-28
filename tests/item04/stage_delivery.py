"""Stage only item four; verify exact evidence, no credentials/PDFs, preserve prior work."""
import hashlib
import json
import subprocess
import sys
from common import ROOT,BASE,digest,write
from runtime_probe import CORE,FRONT
sys.path.insert(0,str(ROOT/'tests/item02'))
from local_environment import configured_environment

EXACT={'.gitattributes','tests/test_item04_discovery.py','test-records/第4项报告.md'}|{'backend/scholar_graph/'+f for f in CORE}|{'frontend/'+f for f in FRONT}
PREFIX=('tests/item04/','test-records/item04-20261028/')
def allowed(path):return path in EXACT or path.startswith(PREFIX)
def git(*args):return subprocess.check_output(['git',*args],cwd=ROOT)

if __name__=='__main__':
    assert git('rev-parse','HEAD').decode().strip()=='81b9e0d6b16fa336a522107d9f2d1f17f17fd876'
    assert not git('diff','--cached','--name-only')
    snapshot=json.loads((BASE/'workspace-before.json').read_text(encoding='utf-8'))
    unchanged={p:sha for p,sha in snapshot['files'].items() if not allowed(p)}
    assert all((ROOT/p).is_file() and digest(ROOT/p)==sha for p,sha in unchanged.items()),'Unrelated baseline changed'
    write(BASE/'unrelated-before-commit.json',unchanged)
    subprocess.run(['git','add','--',*sorted(EXACT),'tests/item04','test-records/item04-20261028'],cwd=ROOT,check=True,capture_output=True)
    subprocess.run(['git','add','--renormalize','--','test-records/item04-20261028'],cwd=ROOT,check=True,capture_output=True)
    files=[p for p in git('diff','--cached','--name-only','-z').decode('utf-8').split('\0') if p]
    key=configured_environment()['DEEPSEEK_API_KEY'].encode();assert key
    for path in files:
        assert allowed(path) and not path.lower().endswith('.pdf') and not path.startswith('pdf/'),path
        assert key not in git('show',':'+path),path
    manifest=json.loads((ROOT/'test-records/item04-20261028/manifest.json').read_text(encoding='utf-8'))
    for item in manifest['files']:
        content=git('show',':test-records/item04-20261028/'+item['path'])
        assert len(content)==item['bytes'] and hashlib.sha256(content).hexdigest()==item['sha256'],item['path']
    subprocess.run(['git','diff','--cached','--check'],cwd=ROOT,check=True)
    value={'staged_files':len(files),'staged_pdf_count':0,'configured_key_occurrences':0,'manifest_entries_match':len(manifest['files']),
           'preexisting_unrelated_files_unchanged':len(unchanged)}
    write(BASE/'stage-check.json',value);print(json.dumps(value))

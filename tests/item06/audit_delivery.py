"""Read-only staged scope, actual credential, unchanged work and evidence verification."""
import json,subprocess,hashlib
from common import ROOT,BASE,write,digest,configured_environment
if __name__=='__main__':
    scope=set(json.loads((BASE/'code-scope.json').read_text(encoding='utf8')))
    staged=subprocess.check_output(['git','diff','--cached','--name-only','-z'],cwd=ROOT).decode().strip('\0').split('\0')
    assert staged and all(p in scope or p=='test-records/第6项报告.md' or p.startswith('test-records/item06-20261029/') for p in staged)
    assert not any(p.lower().endswith('.pdf') for p in staged)
    before=json.loads((BASE/'workspace-before.json').read_text(encoding='utf8'))
    unchanged={p:sha for p,sha in before['files'].items() if p not in scope}
    assert all((ROOT/p).is_file() and digest(ROOT/p)==sha for p,sha in unchanged.items())
    assert all(digest(ROOT/'pdf'/p)==sha for p,sha in before['pdfs'].items())
    credential=configured_environment().get('DEEPSEEK_API_KEY','').encode();assert len(credential)>=8
    staged_hashes={}
    for p in staged:
        value=subprocess.check_output(['git','show',':'+p],cwd=ROOT);assert credential not in value,'Configured key in staged content'
        staged_hashes[p]=hashlib.sha256(value).hexdigest()
    path=ROOT/'test-records/item06-20261029/evidence-manifest.json'
    if path.exists():
        manifest=json.loads(path.read_text(encoding='utf8'))
        assert all(staged_hashes['test-records/item06-20261029/'+name]==sha for name,sha in manifest.items())
    report={'staged_files':len(staged),'staged_pdf_files':0,'configured_key_found':False,'pre_existing_unrelated_files_unchanged':len(unchanged),
        'adopted_related_files':[p for p in before['files'] if p in scope],'manifest_verified':path.exists(),'staged_sha256':staged_hashes}
    write(BASE/'delivery-audit.json',report);print(json.dumps({k:v for k,v in report.items() if k not in ['adopted_related_files','staged_sha256']}))

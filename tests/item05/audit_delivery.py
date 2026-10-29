"""Read-only staged-scope, credential and pre-existing-work verification."""
import json,subprocess,hashlib
from common import ROOT,BASE,configured_environment,write,digest
if __name__=='__main__':
    scope=set(json.loads((BASE/'code-scope.json').read_text(encoding='utf8')))
    staged=subprocess.check_output(['git','diff','--cached','--name-only','-z'],cwd=ROOT).decode().strip('\0').split('\0')
    assert staged and all(p in scope or p=='test-records/第5项报告.md' or p.startswith('test-records/item05-20261029/') for p in staged)
    assert not any(p.lower().endswith('.pdf') for p in staged)
    before=json.loads((BASE/'workspace-before.json').read_text(encoding='utf8'))
    untouched={p:sha for p,sha in before['files'].items() if p not in scope}
    changed=[p for p,sha in untouched.items() if not (ROOT/p).is_file() or digest(ROOT/p)!=sha]
    assert not changed,changed
    env=configured_environment();key=env.get('DEEPSEEK_API_KEY','').encode();assert len(key)>=8
    blobs={}
    for p in staged:
        value=subprocess.check_output(['git','show',':'+p],cwd=ROOT)
        assert key not in value,'Configured credential found in staged content'
        blobs[p]=hashlib.sha256(value).hexdigest()
    manifest=ROOT/'test-records/item05-20261029/evidence-manifest.json'
    if manifest.exists():
        entries=json.loads(manifest.read_text(encoding='utf8'))
        for name,sha in entries.items():
            p='test-records/item05-20261029/'+name
            assert blobs[p]==sha,(p,'staged evidence differs from manifest')
    report={'staged_files':len(staged),'staged_pdf_files':0,'configured_key_found':False,'pre_existing_unrelated_files_unchanged':len(untouched),
        'adopted_pre_existing_related_files':[p for p in before['files'] if p in scope],
        'manifest_verified':manifest.exists(),'staged_sha256':blobs}
    write(BASE/'delivery-audit.json',report)
    print(json.dumps({k:v for k,v in report.items() if k not in ['staged_sha256','adopted_pre_existing_related_files']}))

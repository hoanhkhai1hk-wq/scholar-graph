"""Stage only this UI item and inspect exact staged bytes for disclosure."""
import json
import subprocess
from common import ROOT, BASE, digest, write, configured_environment

def git(*args):
    return subprocess.check_output(['git',*args],cwd=ROOT)

before=json.loads((BASE/'workspace-before.json').read_text(encoding='utf8'))
dirty_before=set(n.replace('\\','/') for n in before['files'])
changed=git('diff','--name-only','HEAD','--','frontend').decode().splitlines()
exact={n for n in changed if n not in dirty_before}
exact.update(['.gitattributes','PRODUCT.md','DESIGN.md','.impeccable/design.json',
              'frontend/app/celadon.css','frontend/components/AsyncStatus.tsx',
              'docs/ui-celadon-surface.md','docs/ui-design-proposals.md','docs/ui-design-preview.html',
              'docs/ui-design-audit-before.md','docs/ui-design-evidence.json','docs/ui-polish-acceptance.md'])
prefixes=('tests/ui_celadon/','test-records/ui-celadon-20261029/',
          'docs/images/ui-celadon-20261029/','docs/images/ui-design-20261029/')
allowed=lambda p:p in exact or p.startswith(prefixes)
already=git('diff','--cached','--name-only').decode().splitlines()
assert all(allowed(n) for n in already),'Unrelated pre-staged files; preserve and inspect before proceeding'
subprocess.run(['git','add','--',*sorted(exact),*[n.rstrip('/') for n in prefixes]],cwd=ROOT,check=True,capture_output=True)
subprocess.run(['git','add','--renormalize','--','test-records/ui-celadon-20261029'],cwd=ROOT,check=True,capture_output=True)
staged=git('diff','--cached','--name-only').decode().splitlines()
assert all(allowed(n) for n in staged)
assert not any(n.lower().endswith('.pdf') or n.startswith('pdf/') or n in ['.env','docker-compose.override.yml','.env.example','.gitignore','README.md','frontend/components/UploadForm.tsx'] for n in staged)
key=configured_environment().get('DEEPSEEK_API_KEY','').encode()
for n in staged:
    value=git('show',':'+n)
    assert not key or key not in value,'Credential in staged content: '+n
manifest=json.loads((ROOT/'test-records/ui-celadon-20261029/manifest.json').read_text(encoding='utf8'))
for row in manifest:
    value=git('show',':test-records/ui-celadon-20261029/'+row['path'])
    import hashlib
    assert hashlib.sha256(value).hexdigest()==row['sha256'],row['path']
write(BASE/'staged-check.json',{'passed':True,'files':len(staged),'staged_paths':staged,'secret_scan':'passed','pdfs':0,'unrelated_changes_staged':0,'evidence_manifest_verified':len(manifest)})
print(json.dumps({'staged_files':len(staged),'secret_scan':'passed','pdfs':0,'unrelated_changes_staged':0,'manifest_entries_verified':len(manifest)}))

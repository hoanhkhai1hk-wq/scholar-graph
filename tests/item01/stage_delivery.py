"""Stage the reviewed item-1 selection; never stage local papers or credentials."""
import hashlib
import json
import os
from pathlib import Path
import subprocess

ROOT=Path(__file__).resolve().parents[2]; BASE=ROOT/'data/item01-20261028'

def git(*args): return subprocess.check_output(['git',*args],cwd=ROOT)

def main():
    chosen=set(json.loads((BASE/'selected-paths.json').read_text(encoding='utf-8')))
    for directory in ['tests/item01','test-records/item01-20261028']:
        chosen.update(p.relative_to(ROOT).as_posix() for p in (ROOT/directory).rglob('*') if p.is_file())
    chosen.add('test-records/第1项报告.md')
    chosen.add('.gitattributes')
    chosen={p for p in chosen if (ROOT/p).is_file()}
    for name in chosen:
        path=Path(name)
        if path.suffix.lower()=='.pdf' or any(part in {'pdf','data','.git','node_modules'} for part in path.parts) or path.name.startswith('.env'):
            raise ValueError('Forbidden local/sensitive path in selection')
    staged=set(git('diff','--cached','--name-only','-z').decode('utf-8').split('\0'))-{''}
    if staged-chosen: raise RuntimeError('Existing unrelated staged files must remain untouched')
    credentials={}
    for line in (ROOT/'.env').read_text(encoding='utf-8-sig').splitlines():
        if '=' not in line or line.lstrip().startswith('#'): continue
        name,value=line.split('=',1); value=value.strip().strip(chr(34)).strip(chr(39))
        if name.strip() in {'DEEPSEEK_API_KEY','SG_REVIEW_CODE','SG_SERVICE_TOKEN'} and value:
            credentials[name.strip()]=value.encode('utf-8')
    for name in chosen:
        payload=(ROOT/name).read_bytes()
        if any(secret in payload for secret in credentials.values()):
            raise RuntimeError('Credential value detected in selected file; value not printed')
    dirty=set(git('diff','--name-only','-z').decode('utf-8').split('\0'))|set(git('ls-files','--others','--exclude-standard','-z').decode('utf-8').split('\0'))
    unrelated={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in dirty-chosen-{''}
               if (ROOT/p).is_file() and not p.startswith('.playwright-mcp/')}
    (BASE/'unrelated-source-hashes.json').write_text(json.dumps(unrelated,ensure_ascii=False,indent=2),encoding='utf-8')
    paths=BASE/'stage-paths.nul'; paths.write_bytes(b'\0'.join(p.encode('utf-8') for p in sorted(chosen))+b'\0')
    result=subprocess.run(['git','add','--pathspec-from-file='+str(paths),'--pathspec-file-nul'],cwd=ROOT,capture_output=True)
    (BASE/'git-stage.log').write_bytes(result.stdout+result.stderr)
    if result.returncode: raise RuntimeError('Git staging failed; inspect local stage log')
    # Applying a new -text attribute does not invalidate an already staged
    # file's stat cache; explicitly refresh the raw logs without changing bytes.
    logs=sorted(p for p in chosen if p.startswith('test-records/item01-20261028/') and p.endswith('.log'))
    log_paths=BASE/'stage-log-paths.nul'; log_paths.write_bytes(b'\0'.join(p.encode('utf-8') for p in logs)+b'\0')
    subprocess.run(['git','add','--renormalize','--pathspec-from-file='+str(log_paths),'--pathspec-file-nul'],cwd=ROOT,check=True,capture_output=True)
    actual=set(git('diff','--cached','--name-only','-z').decode('utf-8').split('\0'))-{''}
    for name in actual:
        payload=git('show',':'+name)
        if any(secret in payload for secret in credentials.values()): raise RuntimeError('Staged credential value detected; value not printed')
        if name in logs and payload!=(ROOT/name).read_bytes(): raise RuntimeError('Raw log staging changed bytes')
    subprocess.run(['git','diff','--cached','--check'],cwd=ROOT,check=True)
    audit={'scanned_staged_files':len(actual),'staged_pdf_files':0,'credential_value_matches':0,
           'unrelated_worktree_files_preserved':len(unrelated),'raw_logs_byte_identical':True,'paths':sorted(actual),
           'scope_notice':'Includes existing runtime dependencies of the item-1 workspace; does not certify other PDF sections.'}
    output=ROOT/'test-records/item01-20261028/source-and-sensitive-audit.json'
    output.write_text(json.dumps(audit,ensure_ascii=False,indent=2),encoding='utf-8')
    subprocess.run(['git','add','--',str(output)],cwd=ROOT,check=True,capture_output=True)
    print(json.dumps({k:v for k,v in audit.items() if k!='paths'},ensure_ascii=False),flush=True)

if __name__=='__main__': main()

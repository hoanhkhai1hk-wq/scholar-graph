"""Stage only item 2 and check private-input exclusion before the authorized commit."""
import hashlib
import argparse
import json
from pathlib import Path
import subprocess
from local_environment import configured_environment

ROOT=Path(__file__).resolve().parents[2]; BASE=ROOT/'data/item02-20261028'
EXACT={'.gitattributes','backend/scholar_graph/qa_sse.py','backend/scholar_graph/vector_worker.py',
       'backend/scholar_graph/workspace_research.py','frontend/app/qa/page.tsx','frontend/components/LayoutViewer.tsx',
       'tests/test_compare_sse.py','tests/test_item02_research.py','tests/test_workspace_research.py','test-records/第2项报告.md'}
PREFIX=('tests/item02/','test-records/item02-20261028/')


def git(*args): return subprocess.check_output(['git',*args],cwd=ROOT)
def allowed(path): return path in EXACT or path.startswith(PREFIX)


def main():
    parser=argparse.ArgumentParser(); parser.add_argument('--label',default=''); args=parser.parse_args()
    assert not args.label or all(c.isascii() and (c.isalnum() or c in '-_') for c in args.label)
    prefix=args.label+'-' if args.label else ''
    assert not git('diff','--cached','--name-only','-z'),'Existing staged changes must remain separate.'
    names=git('ls-files','-m','-o','--exclude-standard','-z').decode('utf-8').split('\0')
    unrelated={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in names if p and not allowed(p) and (ROOT/p).is_file()}
    (BASE/(prefix+'unrelated-before-commit.json')).write_text(json.dumps(unrelated,ensure_ascii=False,indent=2),encoding='utf-8')
    paths=[*sorted(EXACT),'tests/item02','test-records/item02-20261028']
    subprocess.run(['git','add','--',*paths],cwd=ROOT,check=True,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
    # Preserve CR/LF in every evidence file, so its manifest hash survives Git.
    evidence=[p.relative_to(ROOT).as_posix() for p in (ROOT/'test-records/item02-20261028').rglob('*') if p.is_file()]
    subprocess.run(['git','add','--renormalize','--',*evidence],cwd=ROOT,check=True,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
    staged=[p for p in git('diff','--cached','--name-only','-z').decode('utf-8').split('\0') if p]
    assert staged and all(allowed(p) for p in staged)
    assert all(not p.lower().endswith('.pdf') and not p.startswith('pdf/') for p in staged)
    private_key=configured_environment().get('DEEPSEEK_API_KEY','').encode()
    assert private_key
    for path in staged:
        content=git('show',':'+path)
        assert private_key not in content,'Configured credential must never be staged.'
        if path.endswith('.log'):
            assert content==(ROOT/path).read_bytes(),'Log line endings changed: '+path
    manifest=json.loads((ROOT/'test-records/item02-20261028/manifest.json').read_text(encoding='utf-8'))
    for item in manifest['files']:
        content=git('show',':test-records/item02-20261028/'+item['path'])
        assert len(content)==item['bytes'] and hashlib.sha256(content).hexdigest()==item['sha256']
    subprocess.run(['git','diff','--cached','--check'],cwd=ROOT,check=True)
    report={'staged_files':len(staged),'staged_bytes':sum(len(git('show',':'+p)) for p in staged),
            'all_paths_in_item02_scope':True,'original_pdfs_staged':0,'configured_key_occurrences':0,
            'raw_log_bytes_match':True,'unrelated_files_snapshotted':len(unrelated)}
    (BASE/(prefix+'stage-check.json')).write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report))


if __name__=='__main__': main()

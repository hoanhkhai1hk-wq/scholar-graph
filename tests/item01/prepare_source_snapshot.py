"""Review a coherent item-1 source selection without touching unrelated dirty files."""
import argparse
import json
from pathlib import Path
import re
import shutil
import subprocess
import tarfile
import io

ROOT=Path(__file__).resolve().parents[2]
BASE=ROOT/'data/item01-20261028'

def git(*args): return subprocess.check_output(['git',*args],cwd=ROOT).decode('utf-8').split('\0')

def main():
    parser=argparse.ArgumentParser(); parser.add_argument('--run',default='source-snapshot')
    args=parser.parse_args()
    if not re.fullmatch(r'[a-z0-9-]+',args.run): raise ValueError('Use a new local snapshot name')
    dirty=set(git('diff','--name-only','-z')+git('ls-files','--others','--exclude-standard','-z'))-{''}
    selected={p for p in dirty if p.startswith('backend/') and p.endswith('.py')}
    # All registered workspace routers are runtime dependencies of API startup.
    # Keep their existing implementations, without claiming acceptance of 1.2-1.6.
    roots=['app/layout.tsx','app/page.tsx','app/read/[id]/page.tsx','app/upload/page.tsx',
           'app/api/backend/[...path]/route.ts','app/api/workspace/[...path]/route.ts',
           'middleware.ts','app/login/page.tsx','app/settings/page.tsx']
    roots += [p.relative_to(ROOT/'frontend').as_posix() for p in (ROOT/'frontend/app/api/review').rglob('*.ts')]
    queue=[ROOT/'frontend'/p for p in roots]; seen=set()
    while queue:
        file=queue.pop()
        if file in seen or not file.is_file(): continue
        seen.add(file); relative=file.relative_to(ROOT).as_posix()
        if relative in dirty: selected.add(relative)
        for name in re.findall(r'(?:from\s*|import\s*)[\"\']([^\"\']+)[\"\']',file.read_text(encoding='utf-8')):
            if name.startswith('@/'): target=ROOT/'frontend'/name[2:]
            elif name.startswith('.'): target=file.parent/name
            else: continue
            for candidate in (target,*(Path(str(target)+ext) for ext in ['.ts','.tsx','.mjs','.css']),target/'index.ts',target/'index.tsx'):
                if candidate.is_file(): queue.append(candidate.resolve()); break
    selected.update(p for p in dirty if p.startswith('tests/item01/') or p.startswith('test-records/item01-20261028/'))
    extra=['.gitattributes','frontend/app/icon.svg','frontend/package.json','frontend/package-lock.json','frontend/next.config.mjs','frontend/tsconfig.json',
           'frontend/playwright.config.ts','frontend/e2e/item01.spec.ts','frontend/e2e/workbench.spec.ts','pytest.ini',
           'tests/test_engine_session.py','tests/test_item01_parsing_quality.py','tests/test_workspace_formulas.py',
           'tests/test_workspace.py','tests/test_workspace_layout.py','tests/test_workspace_tasks.py','tests/test_bibliography_formats.py',
           'tests/test_page_batches.py','tests/test_reference_identity.py','tests/test_cors.py','tests/test_api_comparison.py',
           'tests/test_tracking_scheduler.py','tests/verify_proxy_compatibility.cjs',
           'scripts/Dockerfile.local-incremental','test-records/第1项报告.md']
    selected.update(p for p in extra if p in dirty)
    snapshot=BASE/args.run; snapshot.mkdir(exist_ok=False)
    archive=subprocess.check_output(['git','archive','HEAD'],cwd=ROOT)
    with tarfile.open(fileobj=io.BytesIO(archive)) as t: t.extractall(snapshot,filter='data')
    for name in selected:
        source=ROOT/name; destination=snapshot/name
        destination.parent.mkdir(parents=True,exist_ok=True); shutil.copyfile(source,destination)
    (BASE/'selected-paths.json').write_text(json.dumps(sorted(selected),ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'selected_files':len(selected),'backend_files':sum(p.startswith('backend/') for p in selected),
                      'frontend_files':sum(p.startswith('frontend/') for p in selected),'snapshot':str(snapshot)},ensure_ascii=False))

if __name__=='__main__': main()

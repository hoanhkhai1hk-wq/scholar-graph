"""Use a new frontend image and cloned data; existing backend release stays fixed."""
import argparse
import shutil
import sqlite3
import subprocess
import time
from common import ROOT, BASE, write, digest, configured_environment

if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('action', choices=['prepare', 'build', 'up', 'release'])
    p.add_argument('--run', required=True)
    a = p.parse_args()
    started = time.monotonic()
    if a.action == 'prepare':
        source, target = ROOT / 'data/item06-20261029/records', BASE / 'records'
        target.mkdir(exist_ok=False)
        for name in ['papers', 'original-pdfs', 'jobs']:
            shutil.copytree(source / name, target / name)
        with sqlite3.connect(source / 'workspace.sqlite3') as src, sqlite3.connect(target / 'workspace.sqlite3') as dst:
            src.backup(dst)
        write(BASE / 'frozen-before.json', {str(p.relative_to(target)).replace('\\', '/'): digest(p)
              for name in ['papers', 'original-pdfs'] for p in (target / name).rglob('*') if p.is_file()})
    elif a.action == 'build':
        folder = BASE / a.run
        folder.mkdir(exist_ok=False)
        shutil.copytree(ROOT / 'frontend/.next', folder / '.next', ignore=shutil.ignore_patterns('cache'))
        for name in ['app', 'components', 'lib', 'public']:
            shutil.copytree(ROOT / 'frontend' / name, folder / name)
        shutil.copyfile(ROOT / 'frontend/next.config.mjs', folder / 'next.config.mjs')
        spec = 'FROM scholar-graph-frontend:code-order-20261029\nWORKDIR /app/frontend\n'
        spec += ''.join('COPY --chown=node:node ' + n + '/ ./' + n + '/\n' for n in ['.next', 'app', 'components', 'lib', 'public'])
        spec += 'COPY --chown=node:node next.config.mjs ./next.config.mjs\n'
        (folder / 'Dockerfile').write_text(spec, encoding='utf8')
        subprocess.run(['docker', 'build', '-t', 'scholar-graph-frontend:celadon-20261029', str(folder)], cwd=ROOT, check=True)
    else:
        configs = [('scholar-graph-ui', ['tests/ui_celadon/compose.yml'])]
        if a.action == 'release':
            configs += [('scholar-graph', ['docker-compose.yml', 'docker-compose.override.yml', 'tests/item05/main-ports.yml']),
                        ('scholar-graph-item04', ['tests/item04/compose.yml']), ('scholar-graph-item05', ['tests/item05/compose.yml']),
                        ('scholar-graph-item06', ['tests/item06/compose.yml']), ('scholar-graph-code-order', ['tests/code_order/compose.yml'])]
        for project, files in configs:
            cmd = ['docker', 'compose', '-p', project]
            for name in files + ['tests/item06/runtime-release.yml', 'tests/code_order/runtime-release.yml', 'tests/ui_celadon/runtime-release.yml']:
                cmd += ['-f', name]
            cmd += ['up', '-d', '--no-build', '--wait']
            subprocess.run(cmd, cwd=ROOT, env=configured_environment(), check=True)
    write(BASE / (a.run + '-result.json'), {'action': a.action, 'exit_code': 0, 'seconds': round(time.monotonic() - started, 3)})

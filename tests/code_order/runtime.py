"""Build/deploy the tested fix without changing any existing library mounts."""
import argparse
import shutil
import subprocess
import time
from common import ROOT, BASE, write, configured_environment

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['backend', 'frontend', 'isolated', 'release'])
    parser.add_argument('--run', required=True)
    args = parser.parse_args()
    started = time.monotonic()
    if args.action in ['backend', 'frontend']:
        folder = BASE / args.run
        folder.mkdir(exist_ok=False)
        service = args.action
        if service == 'backend':
            shutil.copytree(ROOT / 'backend/scholar_graph', folder / 'backend/scholar_graph', ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
            shutil.copytree(ROOT / 'contracts', folder / 'contracts')
            spec = 'COPY --chown=scholar:scholar backend/scholar_graph/ /app/backend/scholar_graph/\nCOPY --chown=scholar:scholar contracts/ /app/contracts/\n'
        else:
            shutil.copytree(ROOT / 'frontend/.next', folder / '.next', ignore=shutil.ignore_patterns('cache'))
            for name in ['app', 'components', 'lib', 'public']:
                shutil.copytree(ROOT / 'frontend' / name, folder / name)
            shutil.copyfile(ROOT / 'frontend/next.config.mjs', folder / 'next.config.mjs')
            spec = 'WORKDIR /app/frontend\n' + ''.join('COPY --chown=node:node ' + name + '/ ./' + name + '/\n' for name in ['.next', 'app', 'components', 'lib', 'public']) + 'COPY --chown=node:node next.config.mjs ./next.config.mjs\n'
        tag = 'scholar-graph-' + service + ':code-order-20261029'
        (folder / 'Dockerfile').write_text('FROM scholar-graph-' + service + ':item06-20261029\n' + spec, encoding='utf8')
        subprocess.run(['docker', 'build', '-t', tag, str(folder)], cwd=ROOT, check=True)
    else:
        configs = [('scholar-graph-code-order', ['tests/code_order/compose.yml'])]
        if args.action == 'release':
            configs += [('scholar-graph', ['docker-compose.yml', 'docker-compose.override.yml', 'tests/item05/main-ports.yml']),
                        ('scholar-graph-item04', ['tests/item04/compose.yml']), ('scholar-graph-item05', ['tests/item05/compose.yml']),
                        ('scholar-graph-item06', ['tests/item06/compose.yml'])]
        commands = []
        for project, files in configs:
            cmd = ['docker', 'compose', '-p', project]
            for file in files + ['tests/item06/runtime-release.yml', 'tests/code_order/runtime-release.yml']:
                cmd += ['-f', file]
            cmd += ['up', '-d', '--no-build', '--wait']
            commands.append(cmd)
            subprocess.run(cmd, cwd=ROOT, env=configured_environment(), check=True)
        write(BASE / (args.run + '-commands.json'), commands)
    write(BASE / (args.run + '-result.json'), {'action': args.action, 'seconds': round(time.monotonic() - started, 3), 'passed': True})

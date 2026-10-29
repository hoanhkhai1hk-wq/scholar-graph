"""Deploy tested images without changing personal/test data locations or provider values."""
import argparse,json,subprocess
from common import ROOT,BASE,configured_environment,write
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--frontend-only',action='store_true');args=p.parse_args()
    commands=[['docker','compose','-p','scholar-graph','-f','docker-compose.yml','-f','docker-compose.override.yml','-f','tests/item05/runtime-release.yml','-f','tests/item05/main-ports.yml','up','-d','--no-build','--wait'],
        ['docker','compose','-p','scholar-graph-item04','-f','tests/item04/compose.yml','-f','tests/item05/runtime-release.yml','up','-d','--no-build','--wait']]
    if args.frontend_only:
        commands.append(['docker','compose','-p','scholar-graph-item05','-f','tests/item05/compose.yml','up','-d','--no-build','--wait'])
        for command in commands:command.extend(['--no-deps','frontend'])
    for command in commands:subprocess.run(command,cwd=ROOT,env=configured_environment(),check=True)
    write(BASE/('release-front-commands.json' if args.frontend_only else 'release-commands.json'),commands)

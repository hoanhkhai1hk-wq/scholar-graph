"""Keep all previous data locations; release the tested writing/chart capabilities."""
import subprocess
from common import ROOT,BASE,write,configured_environment
if __name__=='__main__':
    configurations=[('scholar-graph',['docker-compose.yml','docker-compose.override.yml','tests/item05/main-ports.yml']),
        ('scholar-graph-item04',['tests/item04/compose.yml']),('scholar-graph-item05',['tests/item05/compose.yml']),('scholar-graph-item06',['tests/item06/compose.yml'])]
    commands=[]
    for project,files in configurations:
        command=['docker','compose','-p',project]
        for f in files+['tests/item06/runtime-release.yml']:command.extend(['-f',f])
        command+=['up','-d','--no-build','--wait'];commands.append(command)
        subprocess.run(command,cwd=ROOT,env=configured_environment(),check=True)
    write(BASE/'release-commands.json',commands)

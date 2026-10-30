import argparse
import subprocess
import time
from common import ROOT,BASE,configured_environment,write

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['up','restart']);p.add_argument('--run',required=True);p.add_argument('--updated',action='store_true');a=p.parse_args()
    cmd=['docker','compose','-p','scholar-graph-item08','-f','tests/item08/compose.yml']
    if a.updated:cmd+=['-f','tests/item08/runtime-release.yml']
    started=time.perf_counter()
    if a.action=='up':cmd+=['up','-d','--no-build','--wait']
    else:cmd+=['restart','backend','frontend']
    with (BASE/(a.run+'.log')).open('w',encoding='utf8') as log:
        result=subprocess.run(cmd,cwd=ROOT,env=configured_environment(),stdout=log,stderr=subprocess.STDOUT)
    write(BASE/(a.run+'-result.json'),{'action':a.action,'exit_code':result.returncode,'seconds':time.perf_counter()-started})
    raise SystemExit(result.returncode)

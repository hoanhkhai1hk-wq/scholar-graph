"""Diagnose a real open-pipe session, unlike communicate() which closes stdin."""
import json
import os
from pathlib import Path
import select
import subprocess
import sys
import time

root=Path('/tmp/item01-probe')
command=[sys.executable,'-c',"import faulthandler,runpy,sys; faulthandler.dump_traceback_later(15); sys.path.insert(0,'/app/backend/scholar_graph'); runpy.run_path('/app/backend/scholar_graph/_engine_session_worker.py',run_name='__main__')"]
env={k:v for k,v in os.environ.items() if not any(x in k.upper() for x in ('API_KEY','TOKEN','SECRET','PASSWORD'))}
with (root/'open-pipe.stderr').open('wb') as err:
    p=subprocess.Popen(command,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=err,env=env,cwd=root)
    started=time.monotonic()
    try:
        p.stdin.write((json.dumps({'id':1,'path':str(root/'batch.pdf'),'mode':'mineru','language':'en','pages':[]})+'\n').encode()); p.stdin.flush()
        ready=select.select([p.stdout],[],[],25)[0]
        if ready:
            data=os.read(p.stdout.fileno(),1024*1024)
            print('RESPONSE',len(data),'seconds',time.monotonic()-started,flush=True)
        else: print('NO_RESPONSE',flush=True)
    finally: p.kill(); p.wait(); p.stdin.close(); p.stdout.close()
print((root/'open-pipe.stderr').read_text(errors='replace')[-3500:])

"""Reproduce ordinary Chinese questions against the user's current isolated service."""
import hashlib
import json
import subprocess
import time
from pathlib import Path
import httpx

ROOT=Path(__file__).resolve().parents[2]
BASE=ROOT/'data/qa-usability-20261028'
API='http://127.0.0.1:8100'
def write(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')
def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def client():return httpx.Client(base_url=API,trust_env=False,timeout=240)

def ready(c):
    end=time.monotonic()+60
    while True:
        try:
            if c.get('/api/v2/system',timeout=2).status_code==200:return
        except httpx.HTTPError:pass
        if time.monotonic()>=end:raise RuntimeError('Backend did not become ready within 60 seconds')
        time.sleep(.5)
def snapshot():
    output=BASE/'workspace-before.json';assert not output.exists()
    names=subprocess.check_output(['git','ls-files','-m','-o','--exclude-standard','-z'],cwd=ROOT).decode().split('\0')
    write(output,{'head':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT).decode().strip(),
        'files':{p:digest(ROOT/p) for p in names if p and (ROOT/p).is_file() and not p.startswith('tests/qa_usability/')},
        'pdfs':{p.name:digest(p) for p in (ROOT/'pdf').glob('*.pdf')}})
    print('Preexisting workspace and official PDF hashes saved; no credential values read')

def ask(c,ids,question,out,session=None):
    start=time.monotonic()
    if session is None:
        r=c.post('/api/v2/sessions',json={'paper_ids':ids});r.raise_for_status();session=r.json()['id']
    result={'question':question,'paper_ids':ids,'session_id':session};lines=[];event=None;events=[]
    try:
        with c.stream('POST',f'/api/v2/sessions/{session}/messages/stream',json={'question':question}) as response:
            result['http_status']=response.status_code;response.raise_for_status()
            for line in response.iter_lines():
                lines.append(line)
                if line.startswith('event: '):event=line[7:]
                elif line.startswith('data: '):
                    value=json.loads(line[6:]);events.append({'event':event,'data':value})
                    if event=='final':result['answer']=value
                    elif event=='error':result['error']=value
                    elif event=='done':result['done']=value
    finally:
        result['elapsed_seconds']=round(time.monotonic()-start,3)
        write(out.with_suffix('.json'),result);out.with_suffix('.sse').write_text('\n'.join(lines),encoding='utf-8')
    print(json.dumps({'case':out.name,'seconds':result['elapsed_seconds'],'refused':result.get('answer',{}).get('refused'),'error':result.get('error'),
        'retrieval':result.get('answer',{}).get('metadata',{}).get('retrieval')},ensure_ascii=False),flush=True)
    return result
if __name__=='__main__':snapshot()

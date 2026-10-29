"""Isolated item-five runs and safe provider configuration; never print credentials."""
import hashlib,json,subprocess,sys,time
from pathlib import Path
import httpx
ROOT=Path(__file__).resolve().parents[2];BASE=ROOT/'data/item05-20261029'
API='http://127.0.0.1:8120';WEB='http://127.0.0.1:3420'
sys.path.insert(0,str(ROOT/'tests/item02'))
from local_environment import configured_environment
def write(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf8')
def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def client():return httpx.Client(base_url=API,trust_env=False,timeout=300)
def ready(c):
    end=time.monotonic()+60
    while True:
        try:
            if c.get('/api/v2/system',timeout=2).status_code==200:return
        except httpx.HTTPError:pass
        if time.monotonic()>=end:raise TimeoutError('Backend did not become ready')
        time.sleep(.5)
def wait_task(c,task,out,timeout=2400):
    start=time.monotonic()
    while True:
        write(out,task)
        if task['status'] not in ['queued','running','cancelling']:break
        if time.monotonic()-start>timeout:raise TimeoutError(task['id'])
        time.sleep(2);r=c.get('/api/v2/tasks/'+task['id']);r.raise_for_status();task=r.json()
    print(json.dumps({'task':task['id'],'status':task['status'],'seconds':round(time.monotonic()-start,3),'error':task.get('error')},ensure_ascii=False),flush=True)
    return task
if __name__=='__main__':
    assert not (BASE/'workspace-before.json').exists();BASE.mkdir(exist_ok=True)
    names=subprocess.check_output(['git','ls-files','-m','-o','--exclude-standard','-z'],cwd=ROOT).decode().split('\0')
    write(BASE/'workspace-before.json',{'head':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT).decode().strip(),
        'files':{p:digest(ROOT/p) for p in names if p and (ROOT/p).is_file() and not p.startswith('tests/item05/')},
        'pdfs':{p.name:digest(p) for p in (ROOT/'pdf').glob('*.pdf')}})
    print('Baseline saved; original inputs and existing changes protected')

"""Isolated item-six runtime and evidence; credentials never enter output files."""
import hashlib,json,subprocess,sys,time
from pathlib import Path
import httpx
ROOT=Path(__file__).resolve().parents[2];BASE=ROOT/'data/item06-20261029'
API='http://127.0.0.1:8140';WEB='http://127.0.0.1:3440'
sys.path.insert(0,str(ROOT/'tests/item02'))
from local_environment import configured_environment
def write(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf8')
def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def client():return httpx.Client(base_url=API,trust_env=False,timeout=300)
def ready(c):
    for _ in range(120):
        try:
            if c.get('/api/v2/system',timeout=2).status_code==200:return
        except httpx.HTTPError:pass
        time.sleep(.5)
    raise TimeoutError('Backend not ready')
def wait_task(c,task,path):
    start=time.monotonic()
    while True:
        write(path,task)
        if task['status'] not in ('queued','running','cancelling'):return task
        if time.monotonic()-start>1800:raise TimeoutError(task['id'])
        time.sleep(1);r=c.get('/api/v2/tasks/'+task['id']);r.raise_for_status();task=r.json()
if __name__=='__main__':
    target=BASE/'workspace-before.json';assert not target.exists()
    names=subprocess.check_output(['git','ls-files','-m','-o','--exclude-standard','-z'],cwd=ROOT).decode().split('\0')
    write(target,{'head':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT).decode().strip(),
        'files':{p:digest(ROOT/p) for p in names if p and (ROOT/p).is_file()},
        'pdfs':{p.name:digest(p) for p in (ROOT/'pdf').glob('*.pdf')}})
    print('Saved pre-existing work and original PDF hashes')

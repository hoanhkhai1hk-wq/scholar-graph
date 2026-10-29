"""Run the original future-work flow on a private copy of the first parsed paper."""
import json,os,shutil,sqlite3,sys,time
from common import ROOT,BASE,write,configured_environment
sys.path.insert(0,str(ROOT/'backend'))
if __name__=='__main__':
    out=BASE/'future-before';out.mkdir(exist_ok=False);source=BASE/'records';target=out/'records';target.mkdir()
    shutil.copytree(source/'papers',target/'papers')
    with sqlite3.connect(source/'workspace.sqlite3') as src,sqlite3.connect(target/'workspace.sqlite3') as dst:src.backup(dst)
    env=configured_environment();os.environ.update({k:env[k] for k in ['DEEPSEEK_API_KEY','DEEPSEEK_MODEL']})
    os.environ.update(SCHOLAR_GRAPH_TRACKING_ENABLED='false',SCHOLAR_GRAPH_GROBID_ENABLED='false')
    from fastapi.testclient import TestClient
    from scholar_graph.api import create_app
    with TestClient(create_app(data_dir=target)) as c:
        pid=next(p['id'] for p in c.get('/api/v1/papers').json()['items'] if p['title'] and p['title'].startswith('Attention Is All'))
        start=time.monotonic();r=c.post('/api/v2/writing/tasks',json={'paper_ids':[pid],'kind':'future','idea':'核查作者明确提出的未来研究方向是否已被后续研究尝试。'});r.raise_for_status();task=r.json();write(out/'submission.json',task)
        while task['status'] in ['queued','running','cancelling']:
            time.sleep(2);task=c.get('/api/v2/tasks/'+task['id']).json();write(out/'current.json',task)
        write(out/'result.json',task);print(json.dumps({'status':task['status'],'seconds':round(time.monotonic()-start,3),'result':task.get('result'),'error':task.get('error')},ensure_ascii=False))

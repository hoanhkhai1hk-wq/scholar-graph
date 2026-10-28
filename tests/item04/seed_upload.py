"""One official seed uploaded into item-four's separate library."""
import json
import time
from common import ROOT, BASE, client, digest, wait_task, write

if __name__ == '__main__':
    output = BASE/'seed-upload.json'
    assert not output.exists(), output
    source = ROOT/'pdf/1706.03762v7.pdf'
    sha = digest(source)
    with client() as c, source.open('rb') as f:
        start = time.monotonic()
        r = c.post('/api/v2/uploads', files=[('files',(source.name,f,'application/pdf'))]); r.raise_for_status()
        task = wait_task(c,r.json()['id'],BASE/'seed-upload-task.json')
        assert task['status']=='completed',task
        pid=task['result']['succeeded'][0]['paper_id']
        plan=c.get(f'/api/v2/papers/{pid}/reference-plan');plan.raise_for_status()
        write(BASE/'reference-plan-before.json',plan.json())
        assert digest(source)==sha
        value={'source':source.name,'sha256':sha,'paper_id':pid,'seconds':round(time.monotonic()-start,3),'reference_count':len(plan.json())}
        write(output,value);print(json.dumps(value))

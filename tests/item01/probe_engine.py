"""Real parser diagnostic, stdout contains counts/timing only; dependency errors stay local."""
import json
from pathlib import Path
import subprocess
import sys
import time

import pypdfium2 as pdfium

root=Path('/tmp/item01-probe'); root.mkdir(exist_ok=True)
source=pdfium.PdfDocument(str(root/'book.pdf')); part=pdfium.PdfDocument.new()
try:
    part.import_pages(source,list(range(32))); part.save(str(root/'batch.pdf'))
finally: part.close(); source.close()
request={'id':1,'path':str(root/'batch.pdf'),'mode':'mineru','language':'en','pages':[]}
env={k:v for k,v in __import__('os').environ.items() if not any(x in k.upper() for x in ('API_KEY','TOKEN','SECRET','PASSWORD'))}
for name,command,data in [
    ('one-shot',[sys.executable,'/app/backend/scholar_graph/_engine_worker.py',str(root/'batch.pdf'),'mineru','en','[]'],None),
    ('session',[sys.executable,'/app/backend/scholar_graph/_engine_session_worker.py'],json.dumps(request).encode()+b'\n')]:
    started=time.monotonic()
    try:
        result=subprocess.run(command,input=data,capture_output=True,timeout=75,env=env,cwd=root)
        (root/(name+'.stderr')).write_bytes(result.stderr)
        (root/(name+'.stdout')).write_bytes(result.stdout)
        value=json.loads(result.stdout)
        print(json.dumps({'mode':name,'seconds':round(time.monotonic()-started,3),'returncode':result.returncode,
                          'pages':len(value.get('result',value).get('pages',[]))}),flush=True)
    except subprocess.TimeoutExpired as e:
        (root/(name+'.stderr')).write_bytes(e.stderr or b'')
        print(json.dumps({'mode':name,'seconds':round(time.monotonic()-started,3),'timeout':True}),flush=True)

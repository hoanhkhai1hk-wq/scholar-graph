"""Official Attention topology, real 3D caption, and task-four-derived back translation."""
import base64
import hashlib
import json
import os
import struct
import sys
import time
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'backend'))
from fastapi.testclient import TestClient
from scholar_graph.api import create_app
from scholar_graph.validation import ContractGate

BASELINE='0d81daf0aac3c6fa10f5d418e1026fcf4dbb7f64'
CSV=b'epoch,Base,Big\n1,12,20\n2,18,24\n3,21,26\n4,22.5,27\n'


def digest(raw):return hashlib.sha256(raw).hexdigest()


def save(path,value):
    raw=json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n'
    key=os.environ.get('DEEPSEEK_API_KEY')
    if key and key in raw:raise RuntimeError('Credential safety check rejected report')
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(raw,encoding='utf-8')


def architecture(bundle):
    chunks=bundle['chunks']
    def find(phrase):
        return next(c['chunk_id'] for c in chunks if phrase.casefold() in c['text'].casefold())
    enc,dec,memory,emb,pos=(find(s) for s in ('encoder is composed','decoder is also composed',
                            'queries come from the previous decoder layer','we use learned embeddings','positional encodings'))
    specs=[
      ('inputs','Input tokens',0,0,[emb]),('embenc','Input embedding + position',0,1,[emb,pos]),
      ('encatt','Encoder self-attention',0,2,[enc]),('encnorm','Encoder Add & Norm',0,3,[enc]),
      ('encff','Encoder feed-forward',0,4,[enc]),('encout','Encoder Add & Norm / memory',0,5,[enc]),
      ('shifted','Shifted output tokens',1,0,[dec]),('embdec','Output embedding + position',1,1,[emb,pos]),
      ('masked','Masked self-attention',1,2,[dec]),('decnorm','Decoder Add & Norm',1,3,[dec]),
      ('cross','Encoder-decoder attention',1,4,[memory]),('crossnorm','Cross-attention Add & Norm',1,5,[dec]),
      ('decff','Decoder feed-forward',1,6,[enc,dec]),('decfinal','Decoder Add & Norm',1,7,[dec]),
      ('linear','Linear + Softmax',1,8,[emb]),('prob','Next-token probabilities',1,9,[emb])]
    nodes=[{'id':i,'label':label,'column':col,'row':row,'source_chunk_ids':refs} for i,label,col,row,refs in specs]
    edges=[]
    def edge(a,b,label,cids):edges.append({'from_id':a,'to_id':b,'label':label,'source_chunk_ids':cids})
    for a,b in zip([s[0] for s in specs[:6]],[s[0] for s in specs[1:6]]):edge(a,b,'flow',[enc,emb])
    for a,b in zip([s[0] for s in specs[6:]],[s[0] for s in specs[7:]]):edge(a,b,'flow',[dec,emb])
    edge('encout','cross','keys and values',[memory])
    for a,b in [('embenc','encnorm'),('encnorm','encout')]:edge(a,b,'residual',[enc])
    for a,b in [('embdec','decnorm'),('decnorm','crossnorm'),('crossnorm','decfinal')]:edge(a,b,'residual',[dec])
    return {'paper_ids':[bundle['paper_meta']['id']],'logic':{'nodes':nodes,'edges':edges},'formats':['tikz','dot','mermaid']}


def prior_source(scope):
    path=ROOT/f'data/translation-acceptance/{scope}-response.json'
    value=json.loads(path.read_text(encoding='utf-8'))
    old=json.loads((ROOT/'tests/reports/translation-live-results.json').read_text(encoding='utf-8'))
    manifest=next(c['manifest'] for c in old['runs'][-1]['cases'] if c['request']['scope']==scope)
    actual=[{'source_chunk_id':s['source_chunk_id'],'page_number':s['page_number'],
             'source_sha256':digest(s['source_text'].encode()),'translation_sha256':digest(s['translated_text'].encode())}
            for s in value['segments']]
    if manifest!=actual:raise RuntimeError('Task-four Chinese artifact does not match committed manifest')
    return value,{'path':path.relative_to(ROOT).as_posix(),'response_sha256':digest(path.read_bytes()),
                  'previous_manifest_matched':True,'segments':len(actual)}


def main():
    output=ROOT/'tests/reports/module6-completion-results.json'
    result=json.loads(output.read_text(encoding='utf-8')) if output.is_file() else {'baseline':BASELINE,'runs':[]}
    run={'status':'running','environment':{n:'已设置' if os.environ.get(n) else '未设置' for n in ('DEEPSEEK_API_KEY','DEEPSEEK_MODEL')},'cases':[],
         'implementation_sha256':{p:digest((ROOT/p).read_bytes().replace(b'\r\n',b'\n')) for p in (
             'backend/scholar_graph/topology.py','backend/scholar_graph/charts_3d.py','backend/scholar_graph/translation.py')}}
    result['runs'].append(run)
    app=create_app(data_dir=ROOT/'data/real-model/records')
    pid=json.loads((ROOT/'data/real-model/sources.json').read_text(encoding='utf-8'))['attention_id']
    bundle=app.state.repository.paper(pid)
    with (ROOT/'pdf/1706.03762v7.pdf').open('rb') as source_file:
        pdf_hash=hashlib.file_digest(source_file,'sha256').hexdigest()
    if pdf_hash!=bundle['paper_meta']['file_hash']:raise RuntimeError('Official PDF hash differs from parsed source')
    run.update(source='官方 pdf/ 真文件Attention v7已解析记录；未重新解析PDF',paper_id=pid,pdf_sha256=pdf_hash)
    client=TestClient(app)
    body=architecture(bundle)
    start=time.perf_counter()
    response=client.post('/api/v1/topologies',json=body)
    value=response.json()
    case={'name':'topology','http_status':response.status_code,'elapsed_seconds':round(time.perf_counter()-start,6),
          'status':'passed' if response.status_code==200 and len(value.get('scripts',[]))==3 else 'failed'}
    if case['status']=='passed':
        save(ROOT/'tests/reports/module6-topology.json',{'request':body,'response':value})
        for script in value['scripts']:
            ext={'tikz':'tex','dot':'dot','mermaid':'mmd'}[script['format']]
            (ROOT/f'tests/reports/module6-topology.{ext}').write_text(script['script'],encoding='utf-8')
        case.update(nodes=len(value['nodes']),edges=len(value['edges']),validation=[s['validation']|{'format':s['format']} for s in value['scripts']])
    else:case['error']=value
    run['cases'].append(case)
    save(output,result)
    print(json.dumps(case,ensure_ascii=False),flush=True)
    if not os.environ.get('DEEPSEEK_API_KEY') or not os.environ.get('DEEPSEEK_MODEL'):
        run['cases'].append({'name':'model_cases','status':'skipped','reason':'环境未配置；不伪造图注或回译。'})
        run['status']='skipped'
        save(output,result)
        return 0
    (ROOT/'tests/reports/module6-trends.csv').write_bytes(CSV)
    start=time.perf_counter()
    response=client.post('/api/v1/charts/csv/3d',files={'file':('synthetic-trends.csv',CSV,'text/csv')},
                         data={'value_columns':'["Base","Big"]','x_column':'epoch'})
    value=response.json()
    case={'name':'chart_3d','http_status':response.status_code,'status':'passed' if response.status_code==200 else 'failed',
          'elapsed_seconds':round(time.perf_counter()-start,6),'data_origin':'自制演示CSV，非论文实验值'}
    if response.status_code==200:
        ContractGate().record('ChartOutput',value['chart'])
        save(ROOT/'data/module6-completion/chart3d-response.json',value)
        image=base64.b64decode(value['chart']['image_ref'].split(',')[1])
        (ROOT/'tests/reports/module6-3d-bar.png').write_bytes(image)
        case.update(data_table=value['data_table'],caption=value['chart']['caption'],conclusions=value['conclusions'],
                    numeric_checks=value['chart']['numeric_checks'],metadata=value['metadata'],
                    png={'sha256':digest(image),'bytes':len(image),'width':struct.unpack('>I',image[16:20])[0],
                         'height':struct.unpack('>I',image[20:24])[0],'path':'tests/reports/module6-3d-bar.png'})
    else:case['error']=value
    run['cases'].append(case)
    save(output,result)
    print(json.dumps({k:case[k] for k in ('name','status','http_status','elapsed_seconds')},ensure_ascii=False),flush=True)
    for scope in ('abstract','full'):
        chinese,proof=prior_source(scope)
        start=time.perf_counter()
        response=client.post(f'/api/v1/papers/{pid}/translate',json={'scope':scope,'target':'en','source_translation':chinese})
        value=response.json()
        case={'name':'back_translation_'+scope,'http_status':response.status_code,'status':'passed' if response.status_code==200 else 'failed',
              'elapsed_seconds':round(time.perf_counter()-start,6),'chinese_input_proof':proof}
        if response.status_code==200:
            save(ROOT/f'data/module6-completion/en-{scope}-response.json',value)
            manifest=[{'source_chunk_id':s['source_chunk_id'],'source_sha256':digest(s['source_text'].encode()),
                       'translation_sha256':digest(s['translated_text'].encode())} for s in value['segments']]
            sample=next(s for s in value['segments'] if len(s['source_text'])>200 and s['type']=='text')
            case.update(segments=len(value['segments']),metadata=value['metadata'],manifest=manifest,
                        markdown_characters=len(value['markdown'] or ''),sample=sample if scope=='abstract' else None)
        else:case['error']=value
        run['cases'].append(case)
        save(output,result)
        print(json.dumps({k:case[k] for k in ('name','status','http_status','elapsed_seconds')},ensure_ascii=False),flush=True)
    client.close()
    run['status']='passed' if all(c['status']=='passed' for c in run['cases']) else 'failed'
    save(output,result)
    return 0 if run['status']=='passed' else 1


if __name__=='__main__':raise SystemExit(main())

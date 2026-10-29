"""Request final scripts for the exact already-model-extracted graph, without another model call."""
import json,subprocess,sys
from common import BASE,client,write,ready
if __name__=='__main__':
    source=json.loads((BASE/'browser-final/topology-task.json').read_text(encoding='utf8'))['result']['topology']
    out=BASE/(sys.argv[1] if len(sys.argv)>1 else 'final-render');out.mkdir(exist_ok=False)
    fields={'nodes':['id','label','column','row','source_chunk_ids'],'edges':['from_id','to_id','label','source_chunk_ids']}
    logic={kind:[{k:row[k] for k in keys} for row in source[kind]] for kind,keys in fields.items()}
    ids=list(dict.fromkeys(a['paper_id'] for n in source['nodes'] for a in n['anchors']))
    with client() as c:
        ready(c);r=c.post('/api/v1/topologies',json={'paper_ids':ids,'logic':logic,'formats':['tikz','dot','mermaid','matplotlib']});r.raise_for_status();value=r.json()
    assert value['nodes']==source['nodes'] and value['edges']==source['edges'];write(out/'topology-response.json',value)
    for s in value['scripts']:(out/('topology.'+{'tikz':'tex','dot':'dot','mermaid':'mmd','matplotlib':'py'}[s['format']])).write_text(s['script'],encoding='utf8')
    with (out/'matplotlib-render.log').open('w',encoding='utf8') as log:r=subprocess.run([sys.executable,'topology.py'],cwd=out,stdout=log,stderr=subprocess.STDOUT,timeout=90)
    assert r.returncode==0;write(out/'same-model-logic.json',{'nodes':len(value['nodes']),'edges':len(value['edges']),'identical_nodes_and_edges_to_native_model_task':True,'model_calls':0,'matplotlib_render_exit':r.returncode})

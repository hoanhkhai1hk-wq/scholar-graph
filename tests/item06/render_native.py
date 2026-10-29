"""Execute only the template-generated script that the real browser downloaded."""
import json,subprocess,sys
from common import ROOT,BASE,write
sys.path.insert(0,str(ROOT/'backend'))
from scholar_graph.topology import parse_script
if __name__=='__main__':
    folder=BASE/'browser-final';task=json.loads((folder/'topology-task.json').read_text(encoding='utf8'));topology=task['result']['topology'];graphs=[]
    for script in topology['scripts']:
        ext={'tikz':'tex','dot':'dot','mermaid':'mmd','matplotlib':'py'}[script['format']]
        downloaded=folder/'downloads'/('论文拓扑.'+ext);assert downloaded.read_text(encoding='utf8')==script['script']
        graphs.append(parse_script(script['script'],script['format']))
        (folder/('topology.'+ext)).write_text(script['script'],encoding='utf8')
    assert all(g==graphs[0] for g in graphs)
    with (folder/'matplotlib-render.log').open('w',encoding='utf8') as log:
        r=subprocess.run([sys.executable,'topology.py'],cwd=folder,stdout=log,stderr=subprocess.STDOUT,timeout=90)
    assert r.returncode==0
    write(folder/'script-equivalence.json',{'same_nodes_edges_labels_in_four_formats':True,'nodes':len(graphs[0][0]),'edges':len(graphs[0][1]),'matplotlib_render_exit':r.returncode,'tikz_compiled':False})
    print('Same graph in four formats; downloaded Matplotlib rendered')

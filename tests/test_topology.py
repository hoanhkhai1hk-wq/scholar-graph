import copy
import pytest
from fastapi.testclient import TestClient
from scholar_graph.api import create_app
from scholar_graph.topology import parse_script,generate_topology
from scholar_graph.topology_routes import TopologyRequest
from scholar_graph.errors import PipelineError
from test_validation_status import example_bundle


def topology_api(tmp_path):
    app=create_app(data_dir=tmp_path)
    bundle=example_bundle()
    app.state.repository.store.paper(bundle)
    cid=bundle['chunks'][0]['chunk_id']
    request={'paper_ids':[bundle['paper_meta']['id']],'logic':{
        'nodes':[{'id':'encoder','label':'Encoder','source_chunk_ids':[cid]},
                 {'id':'decoder','label':'Decoder','source_chunk_ids':[cid]}],
        'edges':[{'from_id':'encoder','to_id':'decoder','label':'memory','source_chunk_ids':[cid]}]}}
    return TestClient(app),app,request


def test_three_scripts_roundtrip_nodes_edges_and_real_anchors(tmp_path):
    client,app,body=topology_api(tmp_path)
    response=client.post('/api/v1/topologies',json=body)
    assert response.status_code==200,response.text
    value=response.json()
    assert {s['format'] for s in value['scripts']}=={'dot','tikz','mermaid'}
    for script in value['scripts']:
        nodes,edges=parse_script(script['script'],script['format'])
        assert nodes=={'n0':'Encoder','n1':'Decoder'} and edges==[('n0','n1','memory')]
        assert script['validation']['passed'] and not script['validation']['compiler_executed']
    source=app.state.repository.paper(body['paper_ids'][0])
    for node in value['nodes']:
        app.state.repository.gate.anchor(node['anchors'][0],[source])
    assert '(n0) at (0,0)' in value['scripts'][0]['script']
    assert '(n1) at (0,-2)' in value['scripts'][0]['script']


@pytest.mark.parametrize('kind',['tikz','dot','mermaid'])
@pytest.mark.parametrize('damage',['balance','keyword','endpoint','statement'])
def test_invalid_scripts_never_parse_successfully(tmp_path,kind,damage):
    client,_,body=topology_api(tmp_path)
    value=client.post('/api/v1/topologies',json=body).json()
    script=next(s['script'] for s in value['scripts'] if s['format']==kind)
    if damage=='balance': script+='}'
    if damage=='keyword': script=script.replace({'tikz':'tikzpicture','dot':'digraph','mermaid':'flowchart'}[kind],'UNKNOWN',1)
    if damage=='endpoint':
        if kind=='dot': script=script.replace('n0 -> n1','n0 -> n999')
        elif kind=='mermaid': script=script.replace('| n1','| n999')
        else: script=script.replace('} (n1);','} (n999);')
    if damage=='statement': script+='unsupported command;\n'
    with pytest.raises(PipelineError): parse_script(script,kind)


def test_labels_are_escaped_without_changing_graph(tmp_path):
    client,_,body=topology_api(tmp_path)
    label='end [x] "q" {y} _ % $ & \\ #'
    body['logic']['nodes'][0]['label']=label
    value=client.post('/api/v1/topologies',json=body).json()
    for script in value['scripts']:
        nodes,_=parse_script(script['script'],script['format'])
        assert nodes['n0']==label


@pytest.mark.parametrize('damage',['source','duplicate','edge','formats','both','none'])
def test_bad_topology_inputs_return_uniform_validation_error(tmp_path,damage):
    client,_,body=topology_api(tmp_path)
    if damage=='source':body['logic']['nodes'][0]['source_chunk_ids']=['missing']
    if damage=='duplicate':body['logic']['nodes'][1]['id']='encoder'
    if damage=='edge':body['logic']['edges'][0]['to_id']='missing'
    if damage=='formats':body['formats']=['dot','dot']
    if damage=='both':body['framework']={}
    if damage=='none':body.pop('logic')
    response=client.post('/api/v1/topologies',json=body)
    assert response.status_code==422
    assert set(response.json())=={'error_code','message','details'}


def test_framework_is_supported_without_inventing_causal_edges(tmp_path):
    client,app,body=topology_api(tmp_path)
    framework=client.post('/api/v1/frameworks',json={'paper_ids':body['paper_ids']}).json()
    value=client.post('/api/v1/topologies',json={'paper_ids':body['paper_ids'],'framework':framework}).json()
    assert value['nodes'] and value['metadata']['source']=='framework_chapter_order_not_causality'

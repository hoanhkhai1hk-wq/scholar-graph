"""Protocol/grounding boundaries; real content and rendering are separately exercised."""
import copy,json
from decimal import Decimal
import pytest
from scholar_graph.topology import parse_script
from scholar_graph.workspace_charts import make_chart
from scholar_graph.errors import PipelineError
from scholar_graph.workspace_writing import repair_paragraphs
from test_topology import topology_api

def test_explicit_four_formats_preserve_one_graph_and_legacy_default(tmp_path):
    client,_,body=topology_api(tmp_path)
    assert len(client.post('/api/v1/topologies',json=body).json()['scripts'])==3
    body['formats']=['tikz','dot','mermaid','matplotlib']
    value=client.post('/api/v1/topologies',json=body);assert value.status_code==200
    graphs=[parse_script(s['script'],s['format']) for s in value.json()['scripts']]
    assert all(g==graphs[0] for g in graphs)
    script=value.json()['scripts'][-1]['script']
    with pytest.raises(PipelineError):parse_script(script+'\nimport subprocess\n','matplotlib')

def test_matplotlib_labels_stay_literal_and_broken_script_is_rejected(tmp_path):
    c,_,body=topology_api(tmp_path);body['formats']=['matplotlib']
    label='x " ]; __import__("os"); [ y'
    body['logic']['nodes'][0]['label']=label
    script=c.post('/api/v1/topologies',json=body).json()['scripts'][0]['script']
    assert parse_script(script,'matplotlib')[0]['n0']==label
    with pytest.raises(PipelineError):parse_script(script.replace('json.loads','exec',1),'matplotlib')

@pytest.mark.parametrize('kind',['table','line','bar','radar3d'])
def test_every_chart_has_correct_source_values_and_explanatory_captions(kind):
    raw=b'name,a,b,c\nfirst,1,4,3\nsecond,4,3,3\nthird,9,2,3\n'
    value=make_chart(raw,kind,['a','b','c'],'name')
    assert len(value['data_table']['rows'])==3 and len(value['numeric_checks'])==9
    assert [c['trend'] for c in value['captions']]==['increasing','decreasing','flat']
    for caption,first,last in zip(value['captions'],[1,4,3],[9,2,3]):
        f=caption['numeric_facts'];assert Decimal(f['first']['text'])==first and Decimal(f['last']['text'])==last
        assert Decimal(f['delta']['value'])==last-first
        assert f['first']['anchor']['row_number']==2 and f['last']['anchor']['row_number']==4
        assert '按CSV记录顺序' in caption['text'] and '净变化' in caption['text']
    assert (value['image'] is None)==(kind=='table')

def test_nonmonotonic_data_not_described_as_growth_and_single_row_is_honest():
    c=make_chart(b'a\n2\n1\n3\n','table',['a'])['captions'][0]
    assert c['trend']=='mixed' and '有升有降' in c['text']
    c=make_chart(b'a\n2\n','table',['a'])['captions'][0]
    assert c['trend']=='insufficient_data' and '无法判断' in c['text']

def test_unchanged_paragraph_repair_does_not_repeat_forever():
    draft={'title':'plan','sections':[{'paragraphs':[{'text':'unchanged','type':'proposal','citations':[]}]}]}
    class Client:
        def complete(self,*args,**kwargs):return {'content':json.dumps({'repairs':[{'index':0,'paragraph':copy.deepcopy(draft['sections'][0]['paragraphs'][0])}]})}
    assert repair_paragraphs(Client(),draft,PipelineError('VALIDATION_ERROR','unsupported',details={'paragraph_indices':[0]}),[]) is None

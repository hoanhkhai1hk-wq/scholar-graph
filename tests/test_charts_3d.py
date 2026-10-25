import base64
import copy
import json
import struct
import httpx
import pytest
from fastapi.testclient import TestClient
from scholar_graph.api import create_app
from scholar_graph.charts_3d import generate_3d,validate_3d,source_data
from scholar_graph.deepseek_client import DeepSeekClient
from scholar_graph.errors import PipelineError
from scholar_graph.validation import ContractGate

CSV=b'epoch,Base,Big\n1,12,20\n2,18,24\n3,21,26\n4,22.5,27\n'


def caption_model(monkeypatch,mutate=None,status=200):
    requests=[]
    def handle(request):
        payload=json.loads(json.loads(request.content)['messages'][-1]['content'])
        requests.append(payload)
        if status!=200:return httpx.Response(status,text='private-upstream-body')
        conclusions=[{k:f[k] for k in ('series_name','trend','shape','row_numbers')} | {'text':f['allowed_texts'][0]}
                     for f in payload['facts']]
        if mutate:mutate(conclusions)
        return httpx.Response(200,json={'choices':[{'finish_reason':'stop','message':{'content':json.dumps({'conclusions':conclusions},ensure_ascii=False)}}]})
    client=DeepSeekClient(key='unit-not-real-key',model='deepseek-mock',transport=httpx.MockTransport(handle))
    monkeypatch.setattr('scholar_graph.charts_3d.DeepSeekClient.environment',lambda:client)
    return client,requests


def post(client,raw=CSV,columns=None,x='epoch'):
    data={'value_columns':json.dumps(columns or ['Base','Big'])}
    if x:data['x_column']=x
    return client.post('/api/v1/charts/csv/3d',files={'file':('synthetic-trends.csv',raw,'text/csv')},data=data)


def test_real_3d_png_table_frozen_chart_and_grounded_trend(tmp_path,monkeypatch):
    caption_model(monkeypatch)
    value=post(TestClient(create_app(data_dir=tmp_path))).json()
    ContractGate().record('ChartOutput',value['chart'])
    assert value['projection']=='3d' and value['chart']['chart_type']=='bar'
    image=base64.b64decode(value['chart']['image_ref'].split(',')[1])
    assert image.startswith(b'\x89PNG\r\n\x1a\n') and struct.unpack('>II',image[16:24])==(800,600)
    assert value['data_table']['rows'][0]=={'row_number':2,'values':{'epoch':1,'Base':12,'Big':20}}
    assert '上升' in value['chart']['caption'] and '放缓' in value['chart']['caption']
    assert all(c['row_numbers']==[2,3,4,5] for c in value['conclusions'])
    assert all(c['shape']=='decelerating' and len(c['csv_anchors'])==4 for c in value['conclusions'])
    assert 'unit-not-real-key' not in json.dumps(value)


@pytest.mark.parametrize('values,trend,shape',[
    ([1,2,3],'increasing','constant_rate'),([1,3,7],'increasing','accelerating'),
    ([7,3,1],'decreasing','decelerating'),([3,3,3],'flat','undetermined'),
    ([1,1,2],'nondecreasing','undetermined'),([3,3,2],'nonincreasing','undetermined'),
    ([1,3,2],'mixed','undetermined'),([-1,-2,-4],'decreasing','accelerating')])
def test_exact_fraction_trend_rules(values,trend,shape):
    raw=('v\n'+'\n'.join(map(str,values))+'\n').encode()
    _,_,_,facts=source_data(raw,['v'],None)
    assert facts[0]['trend']==trend and facts[0]['shape']==shape


@pytest.mark.parametrize('damage',['trend','text','rows'])
def test_model_fabrication_or_wrong_provenance_is_rejected(tmp_path,monkeypatch,damage):
    def mutate(items):
        if damage=='trend':items[0]['trend']='decreasing'
        if damage=='text':items[0]['text']='因为模型结构更先进，未来会增长999倍。'
        if damage=='rows':items[0]['row_numbers']=[999]
    _,requests=caption_model(monkeypatch,mutate)
    response=post(TestClient(create_app(data_dir=tmp_path)))
    assert response.status_code==422 and response.json()['error_code']=='CHART_VALIDATION_FAILED'
    assert len(requests)==2 and 'image_ref' not in response.json()


@pytest.mark.parametrize('damage',['table','caption','image','anchor'])
def test_3d_output_gate_rejects_tampering(monkeypatch,damage):
    model,_=caption_model(monkeypatch)
    gate=ContractGate()
    value=generate_3d(CSV,['Base','Big'],'epoch',gate,model)
    if damage=='table':value['data_table']['rows'][0]['values']['Base']=999
    if damage=='caption':value['chart']['caption']='forged'
    if damage=='image':value['chart']['image_ref']='data:image/png;base64,ZmFrZQ=='
    if damage=='anchor':value['conclusions'][0]['csv_anchors'][0]['row_number']=999
    with pytest.raises(PipelineError):validate_3d(value,CSV,['Base','Big'],'epoch',gate)


def test_invalid_csv_missing_key_and_upstream_errors_are_explicit(tmp_path,monkeypatch):
    client=TestClient(create_app(data_dir=tmp_path))
    monkeypatch.delenv('DEEPSEEK_API_KEY',raising=False)
    assert post(client,raw=b'invalid').json()['error_code']=='CSV_INVALID'
    response=post(client)
    assert response.status_code==502 and '环境变量未设置' in response.json()['message']
    caption_model(monkeypatch,status=503)
    response=post(client)
    assert response.status_code==502 and 'private-upstream-body' not in response.text


def test_x_order_insufficient_rows_and_numeric_labels(monkeypatch):
    with pytest.raises(PipelineError):source_data(b'x,y\n2,1\n1,2\n',['y'],'x')
    with pytest.raises(PipelineError):source_data(b'y\n1\n',['y'],None)
    model,_=caption_model(monkeypatch)
    result=generate_3d(b'v1\n1\n2\n3\n',['v1'],None,ContractGate(),model)
    assert result['series_aliases']=={'v1':'系列甲'} and not any(c.isdigit() for c in result['chart']['caption'])


@pytest.mark.real_model
def test_live_3d_trend_caption_requires_real_model(tmp_path,request):
    response=post(TestClient(create_app(data_dir=tmp_path)))
    assert response.status_code==200
    value=response.json()
    assert '上升' in value['chart']['caption'] and all(c['shape']=='decelerating' for c in value['conclusions'])
    request.node.user_properties.extend(('chart3d_'+k,str(v)) for k,v in value['metadata']['model_calls'][-1].items())

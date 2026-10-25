"""Synthetic alignment tests; the acceptance probe uses the previous real zh artifact."""
import copy
import json
import re
import httpx
import pytest
from fastapi.testclient import TestClient
from scholar_graph.api import create_app
from scholar_graph.deepseek_client import DeepSeekClient
from scholar_graph.translation import check_numbers,check_terms
from scholar_graph.errors import PipelineError
from test_translation import api


def prior_chinese(bundle):
    texts={
        'abstract':'编码器和解码器使用注意力，并有12层。',
        'intro':'编码器使用 `print("English")` 和 $x_1 + x_2$。',
        'sub':'```python\nprint("Do not translate")\n```\n解码器使用注意力。',
        'formula':bundle['chunks'][3]['text'],
        'table':'| Model | Score |\n| --- | ---: |\n| 编码器 | 28.4 |'}
    return {'paper_id':bundle['paper_meta']['id'],'scope':'full','target':'zh','markdown':None,'metadata':{},
        'segments':[{'source_chunk_id':c['chunk_id'],'source_text':c['text'],'translated_text':texts[c['chunk_id']],
                     **{k:c[k] for k in ('paper_id','page_number','section_path','type')}} for c in bundle['chunks']]}


def reverse_model(monkeypatch,mutate=None):
    calls=[]
    def handle(request):
        body=json.loads(request.content)
        assert 'Chinese-to-English' in body['messages'][0]['content']
        payload=json.loads(body['messages'][-1]['content'])
        assert all('original_source' in item and re.search(r'[\u3400-\u9fff]',item['original_source']) for item in payload['items'])
        calls.append(payload)
        # Structural protocol MOCK only; never presented as live translation quality.
        rows=[{'id':item['id'],'text':re.sub(r'[\u3400-\u9fff]+',' translated ',item['text'])} for item in payload['items']]
        value={'translations':rows,'terminology':[]}
        if mutate:mutate(value)
        return httpx.Response(200,json={'choices':[{'finish_reason':'stop','message':{'content':json.dumps(value)}}]})
    model=DeepSeekClient(key='unit-en-not-real',model='deepseek-mock',transport=httpx.MockTransport(handle))
    monkeypatch.setattr('scholar_graph.translation.DeepSeekClient.environment',lambda:model)
    return calls


@pytest.mark.parametrize('scope,expected',[('abstract',['abstract']),('full',['abstract','intro','sub','formula','table'])])
def test_reverse_uses_actual_chinese_input_and_preserves_alignment_and_code(tmp_path,monkeypatch,scope,expected):
    client,_,bundle=api(tmp_path)
    source=prior_chinese(bundle)
    reverse_model(monkeypatch)
    response=client.post(f'/api/v1/papers/{bundle["paper_meta"]["id"]}/translate',json={
        'scope':scope,'target':'en','source_translation':source})
    assert response.status_code==200,response.text
    value=response.json()
    assert value['target']=='en' and [s['source_chunk_id'] for s in value['segments']]==expected
    for segment in value['segments']:
        assert segment['source_text']==next(s['translated_text'] for s in source['segments'] if s['source_chunk_id']==segment['source_chunk_id'])
    assert value['metadata']['source_language']=='zh' and value['metadata']['source_translation_sha256']
    if scope=='full':
        assert '`print("English")`' in value['markdown'] and '$x_1 + x_2$' in value['markdown']
        assert '```python\nprint("Do not translate")\n```' in value['markdown']
        assert value['segments'][3]['translated_text']==bundle['chunks'][3]['text']


@pytest.mark.parametrize('damage',['paper','chunk','page','original','duplicate','missing','code','direction'])
def test_unmatched_or_forged_source_alignment_rejected_before_model(tmp_path,monkeypatch,damage):
    client,_,bundle=api(tmp_path)
    source=prior_chinese(bundle)
    if damage=='paper':source['paper_id']='wrong'
    if damage=='chunk':source['segments'][0]['source_chunk_id']='wrong'
    if damage=='page':source['segments'][0]['page_number']=999
    if damage=='original':source['segments'][0]['source_text']='not original'
    if damage=='duplicate':source['segments'].append(copy.deepcopy(source['segments'][0]))
    if damage=='missing':source['segments'].pop(0)
    if damage=='code':source['segments'][1]['translated_text']='代码已被删除。'
    if damage=='direction':source['target']='en'
    calls=reverse_model(monkeypatch)
    response=client.post(f'/api/v1/papers/{bundle["paper_meta"]["id"]}/translate',json={'scope':'full','target':'en','source_translation':source})
    assert response.status_code==422 and not calls


def test_missing_key_never_returns_fake_english(tmp_path,monkeypatch):
    client,_,bundle=api(tmp_path)
    monkeypatch.delenv('DEEPSEEK_API_KEY',raising=False)
    response=client.post(f'/api/v1/papers/{bundle["paper_meta"]["id"]}/translate',json={
        'scope':'abstract','target':'en','source_translation':prior_chinese(bundle)})
    assert response.status_code==502 and response.json()['error_code']=='UPSTREAM_ERROR'


def test_leftover_chinese_from_model_is_rejected(tmp_path,monkeypatch):
    client,_,bundle=api(tmp_path)
    reverse_model(monkeypatch,lambda v:v['translations'][0].update(text='编码器没有翻译，12层。'))
    response=client.post(f'/api/v1/papers/{bundle["paper_meta"]["id"]}/translate',json={
        'scope':'abstract','target':'en','source_translation':prior_chinese(bundle)})
    assert response.status_code==502 and 'segments' not in response.json()


def test_native_chinese_stored_chunks_also_supported(tmp_path,monkeypatch):
    _,_,bundle=api(tmp_path)
    bundle['chunks']=bundle['chunks'][:1]
    bundle['chunks'][0]['text']='编码器和解码器使用注意力，并有12层。'
    app=create_app(data_dir=tmp_path/'native')
    app.state.repository.store.paper(bundle)
    reverse_model(monkeypatch)
    response=TestClient(app).post(f'/api/v1/papers/{bundle["paper_meta"]["id"]}/translate',json={'scope':'abstract','target':'en'})
    assert response.status_code==200 and response.json()['metadata']['source_input']=='stored_chinese_chunks'


@pytest.mark.parametrize('source,english',[('2023年8月2日','2 Aug 2023'),('八块GPU','8 GPUs'),('8块GPU','eight GPUs'),('3600万句子','36 million sentences')])
def test_bidirectional_number_evidence(source,english):
    check_numbers(source,english,'unit')


@pytest.mark.parametrize('translation,valid',[('learn to attend by relative positions',True),('learn relative positions',False)])
def test_attention_verb_is_valid_but_omission_is_rejected(translation,valid):
    if valid: check_terms('进行注意力计算',translation,{'注意力':'attention'})
    else:
        with pytest.raises(PipelineError):check_terms('进行注意力计算',translation,{'注意力':'attention'})


@pytest.mark.parametrize('source,target,english',[
    ('困惑度','perplexity','the reported perplexities'),('数值','values','the measured value'),
    ('矩阵','matrix','several matrices'),('分析','analysis','the analyses')])
def test_english_technical_noun_inflections_are_not_false_rejections(source,target,english):
    check_terms(source,english,{source:target})
    with pytest.raises(PipelineError):check_terms(source,'unrelated text',{source:target})


@pytest.mark.real_model
def test_live_chinese_to_english_requires_actual_model(tmp_path,request):
    client,_,bundle=api(tmp_path)
    path=f'/api/v1/papers/{bundle["paper_meta"]["id"]}/translate'
    chinese=client.post(path,json={'scope':'abstract','target':'zh'})
    assert chinese.status_code==200
    response=client.post(path,json={'scope':'abstract','target':'en','source_translation':chinese.json()})
    assert response.status_code==200
    value=response.json()
    assert 'encoder' in value['segments'][0]['translated_text'].lower() and '12' in value['segments'][0]['translated_text']
    request.node.user_properties.extend(('translation_en_'+k,str(v)) for k,v in value['metadata']['model_calls'][-1].items())

"""Transport/protection tests use self-made contract data, not official PDFs."""
import copy
import json
import re

import httpx
import pytest
from fastapi.testclient import TestClient

from scholar_graph.api import create_app
from scholar_graph.deepseek_client import DeepSeekClient
from scholar_graph.translation import protect, protect_terms, restore, units, Translator, TERMS, check_numbers
from scholar_graph.errors import PipelineError
from test_validation_status import example_bundle


def api(tmp_path):
    app = create_app(data_dir=tmp_path)
    bundle = example_bundle()
    prototype = bundle['chunks'][0]
    specs = [
        ('abstract', ['Abstract'], 'text', 'The encoder and decoder use attention with 12 layers.'),
        ('intro', ['1 Introduction'], 'text', 'The encoder uses `print("English")` and $x_1 + x_2$ in the model.'),
        ('sub', ['1 Introduction', '1.1 Detail'], 'text', '```python\nprint("Do not translate")\n```\nThe decoder uses attention.'),
        ('formula', ['2 Equations'], 'formula', r'\frac{a}{b} = \beta_1 + 0.98'),
        ('table', ['3 Results'], 'table', '| Model | Score |\n| --- | ---: |\n| encoder | 28.4 |'),
    ]
    bundle['chunks'] = []
    for cid, path, kind, text in specs:
        c = copy.deepcopy(prototype)
        c.update(chunk_id=cid, section_path=path, heading_1=path[0],
                 heading_2=path[1] if len(path) > 1 else None, heading_3=None, text=text, type=kind)
        bundle['chunks'].append(c)
    bundle['citation_links'] = []
    app.state.repository.store.paper(bundle)
    return TestClient(app), app, bundle


def gateway(monkeypatch, mutate=None, *, status=200):
    calls = []
    def handle(request):
        body = json.loads(request.content)
        assert body['max_tokens'] == 8192 and body['response_format'] == {'type': 'json_object'}
        data = json.loads(body['messages'][-1]['content'])
        calls.append(data)
        if status != 200:
            return httpx.Response(status, text='private-provider-body')
        rows = []
        for item in data['items']:
            text = item['text']
            pattern = r'__SGKEEP_[a-f0-9]{12}_\d+__'
            if re.sub(pattern, '', text).strip():
                # Deliberately deterministic MOCK translation, never live evidence.
                for source, target in sorted(data['glossary'].items(), key=lambda p: -len(p[0])):
                    text = re.sub(r'(?<![\w-])' + re.escape(source) + r'(?![\w-])', target, text, flags=re.I)
                text = '译文：' + text
            rows.append({'id': item['id'], 'text': text})
        result = {'translations': rows, 'terminology': []}
        if mutate:
            mutate(result, len(calls))
        return httpx.Response(200, json={'choices': [{'finish_reason': 'stop', 'message': {
            'role': 'assistant', 'content': json.dumps(result, ensure_ascii=False)}}],
            'usage': {'prompt_tokens': 12, 'completion_tokens': 8, 'total_tokens': 20}})
    client = DeepSeekClient(key='unit-translation-credential', model='deepseek-mock', transport=httpx.MockTransport(handle))
    monkeypatch.setattr('scholar_graph.translation.DeepSeekClient.environment', lambda: client)
    return client, calls


@pytest.mark.parametrize('scope,options,expected', [
    ('abstract', {}, ['abstract']),
    ('section', {'section_path': ['1 Introduction']}, ['intro', 'sub']),
    ('selection', {'chunk_ids': ['table', 'abstract']}, ['abstract', 'table']),
    ('full', {}, ['abstract', 'intro', 'sub', 'formula', 'table']),
])
def test_scopes_align_one_to_one_in_source_order(tmp_path, monkeypatch, scope, options, expected):
    client, _, bundle = api(tmp_path)
    model, _ = gateway(monkeypatch)
    response = client.post(f'/api/v1/papers/{bundle["paper_meta"]["id"]}/translate',
                           json={'scope': scope, 'target': 'zh', **options})
    assert response.status_code == 200, response.text
    value = response.json()
    assert [s['source_chunk_id'] for s in value['segments']] == expected
    sources = {c['chunk_id']: c for c in bundle['chunks']}
    for segment in value['segments']:
        source = sources[segment['source_chunk_id']]
        assert segment['source_text'] == source['text']
        assert segment['paper_id'] == source['paper_id']
        assert segment['page_number'] == source['page_number']
        assert segment['section_path'] == source['section_path']
    if scope == 'full':
        assert '## 1 Introduction' in value['markdown'] and '### 1.1 Detail' in value['markdown']
        assert '`print("English")`' in value['markdown'] and '$x_1 + x_2$' in value['markdown']
        assert '```python\nprint("Do not translate")\n```' in value['markdown']
        assert sources['formula']['text'] == value['segments'][3]['translated_text']
        assert '| --- | ---: |' in value['markdown'] and '28.4' in value['markdown']
        assert [value['markdown'].index(f'<a id="{cid}"></a>') for cid in expected] == sorted(
            value['markdown'].index(f'<a id="{cid}"></a>') for cid in expected)
    else:
        assert value['markdown'] is None
    assert value['metadata']['model_calls'] == model.calls
    assert 'unit-translation-credential' not in response.text


def test_missing_credentials_and_upstream_errors_are_explicit(tmp_path, monkeypatch):
    client, _, bundle = api(tmp_path)
    path = f'/api/v1/papers/{bundle["paper_meta"]["id"]}/translate'
    monkeypatch.delenv('DEEPSEEK_API_KEY', raising=False)
    response = client.post(path, json={'scope': 'full'})
    assert response.status_code == 502 and response.json()['error_code'] == 'UPSTREAM_ERROR'
    assert '环境变量未设置' in response.json()['message']
    assert set(response.json()) == {'error_code', 'message', 'details'}
    gateway(monkeypatch, status=429)
    response = client.post(path, json={'scope': 'abstract'})
    assert response.status_code == 502 and 'HTTP 429' in response.json()['message']
    assert 'private-provider-body' not in response.text
    assert 'translated_text' not in response.text


@pytest.mark.parametrize('body', [
    {'scope': 'full', 'target': 'en'}, {'scope': 'section'}, {'scope': 'selection'},
    {'scope': 'full', 'section_path': ['Abstract']}, {'scope': 'section', 'section_path': []},
    {'scope': 'abstract', 'chunk_ids': ['abstract']},
    {'scope': 'selection', 'chunk_ids': ['intro', 'intro']},
    {'scope': 'selection', 'chunk_ids': ['unknown']},
    {'scope': 'section', 'section_path': ['Unknown']},
    {'scope': 'selection', 'chunk_ids': ['intro'], 'text': 'unanchored source'},
])
def test_invalid_ranges_and_direction_do_not_call_model(tmp_path, monkeypatch, body):
    client, _, bundle = api(tmp_path)
    def unexpected():
        pytest.fail('bad input must be rejected before model initialization')
    monkeypatch.setattr('scholar_graph.translation.DeepSeekClient.environment', unexpected)
    response = client.post(f'/api/v1/papers/{bundle["paper_meta"]["id"]}/translate', json=body)
    assert response.status_code == 422


def test_missing_paper_is_404_before_model_call(tmp_path):
    client, _, _ = api(tmp_path)
    response = client.post('/api/v1/papers/missing/translate', json={'scope': 'full'})
    assert response.status_code == 404 and response.json()['error_code'] == 'PAPER_NOT_FOUND'


@pytest.mark.parametrize('damage', ['drop', 'duplicate', 'reorder', 'placeholder', 'term', 'empty'])
def test_bad_model_output_is_retried_boundedly_and_never_returned(tmp_path, monkeypatch, damage):
    client, _, bundle = api(tmp_path)
    def mutate(value, count):
        rows = value['translations']
        if damage == 'drop': rows.pop()
        if damage == 'duplicate': rows[1]['id'] = rows[0]['id']
        if damage == 'reorder': rows.reverse()
        if damage == 'placeholder': rows[0]['text'] += '__SGKEEP_012345678abc_0__'
        if damage == 'term': value['terminology'] = [{'source': 'encoder', 'target': '错误术语'}]
        if damage == 'empty': rows[0]['text'] = ''
    _, calls = gateway(monkeypatch, mutate)
    response = client.post(f'/api/v1/papers/{bundle["paper_meta"]["id"]}/translate',
                           json={'scope': 'selection', 'chunk_ids': ['abstract', 'intro']})
    assert response.status_code == 502 and len(calls) == 2
    assert set(response.json()) == {'error_code', 'message', 'details'}
    assert 'segments' not in response.json()


def test_retry_recovers_format_without_faking_success(tmp_path, monkeypatch):
    client, _, bundle = api(tmp_path)
    def mutate(value, count):
        if count == 1:
            value['translations'] = []
    _, calls = gateway(monkeypatch, mutate)
    response = client.post(f'/api/v1/papers/{bundle["paper_meta"]["id"]}/translate', json={'scope': 'abstract'})
    assert response.status_code == 200 and len(calls) == 2
    assert len(response.json()['metadata']['model_calls']) == 2


def test_protection_roundtrip_and_splitting_never_change_code_or_math():
    source = ('A' * 3500 + r'$\beta_1=0.9$' + 'B' * 3500 + '\n'
              '~~~python\nprint("English code")\n~~~\n' + r'Use \[x^2\] and \(y+1\) and `fit()`.'
              '\n<table><tr><td rowspan="2">28.4</td></tr></table>')
    masked, spans = protect(source)
    pieces = units(masked, spans)
    assert ''.join(pieces) == masked
    for token in spans:
        assert sum(token in piece for piece in pieces) == 1
    assert restore(masked, spans) == source
    assert all(len(piece) <= 3000 for piece in pieces)
    assert all(content not in masked for content in (r'$\beta_1=0.9$', 'print("English code")', '<table>'))


def test_large_chunk_is_split_internally_but_one_mapping_returned(tmp_path, monkeypatch):
    _, app, bundle = api(tmp_path)
    model, calls = gateway(monkeypatch)
    source = copy.deepcopy(bundle['chunks'][0])
    source['text'] = ('The encoder uses attention. ' * 400) + '$x_1=12$'
    large_app = create_app(data_dir=tmp_path / 'large')
    large_app.state.repository.store.paper({**bundle, 'chunks': [source]})
    result = Translator(large_app.state.repository, model).translate(bundle['paper_meta']['id'], scope='full')
    assert len(calls) > 1 and len(result['segments']) == 1
    assert result['segments'][0]['source_text'] == source['text']
    assert '$x_1=12$' in result['segments'][0]['translated_text']


def test_established_terms_are_opaque_and_restored_consistently():
    original, code = protect('The encoder uses attention in `encoder()` and $encoder=12$.')
    masked, terms = protect_terms(original, TERMS)
    assert 'encoder' not in masked and 'attention' not in masked
    assert sorted(terms.values()) == ['注意力', '编码器']
    for token, chinese in terms.items():
        masked = masked.replace(token, chinese)
    text = restore(masked, code)
    assert '编码器' in text and '注意力' in text
    assert '`encoder()`' in text and '$encoder=12$' in text


def test_later_batch_failure_never_returns_earlier_translations(tmp_path, monkeypatch):
    client, _, bundle = api(tmp_path)
    def fail(value, count):
        if count >= 2:
            raise httpx.ReadTimeout('private-provider-error')
    _, calls = gateway(monkeypatch, fail)
    # Force batches without requiring an unnecessarily large fixture.
    monkeypatch.setattr('scholar_graph.translation.BATCH_CHARS', 100)
    response = client.post(f'/api/v1/papers/{bundle["paper_meta"]["id"]}/translate', json={'scope': 'full'})
    assert response.status_code == 502 and len(calls) == 2
    assert 'segments' not in response.json() and 'private-provider-error' not in response.text


def test_new_numbers_from_model_are_rejected(tmp_path, monkeypatch):
    client, _, bundle = api(tmp_path)
    gateway(monkeypatch, lambda value, count: value['translations'][0].update(
        text=value['translations'][0]['text'] + ' 新增9999个实验。'))
    response = client.post(f'/api/v1/papers/{bundle["paper_meta"]["id"]}/translate', json={'scope': 'abstract'})
    assert response.status_code == 502
    assert '数字' in response.json()['details']['reason']


def test_missing_abstract_never_invents_a_chunk(tmp_path, monkeypatch):
    _, _, bundle = api(tmp_path)
    app = create_app(data_dir=tmp_path / 'no-abstract')
    bundle['chunks'] = [c for c in bundle['chunks'] if c['chunk_id'] != 'abstract']
    bundle['paper_meta']['abstract'] = 'Metadata is not an anchored original paragraph.'
    app.state.repository.store.paper(bundle)
    model, calls = gateway(monkeypatch)
    response = TestClient(app).post(f'/api/v1/papers/{bundle["paper_meta"]["id"]}/translate', json={'scope': 'abstract'})
    assert response.status_code == 422 and not calls


def test_source_and_time_budgets_fail_explicitly(tmp_path, monkeypatch):
    client, _, bundle = api(tmp_path)
    _, calls = gateway(monkeypatch)
    path = f'/api/v1/papers/{bundle["paper_meta"]["id"]}/translate'
    monkeypatch.setattr('scholar_graph.translation.MAX_SOURCE_CHARS', 1)
    assert client.post(path, json={'scope': 'full'}).status_code == 422
    assert not calls
    monkeypatch.setattr('scholar_graph.translation.MAX_SOURCE_CHARS', 600_000)
    monkeypatch.setattr('scholar_graph.translation.MAX_REQUEST_SECONDS', -1)
    response = client.post(path, json={'scope': 'full'})
    assert response.status_code == 502 and '900秒' in response.json()['message'] and not calls


@pytest.mark.parametrize('source,translated,valid', [
    ('2 Aug 2023', '2023年8月2日', True),
    ('We used eight GPUs.', '我们使用8个GPU。', True),
    ('4.5 million pairs and 36 million pairs.', '450万对和3600万对。', True),
    ('36M sentences.', '3600万句子。', True),
    ('37,000 tokens and 3.5 days.', '37000个词元和3.5天。', True),
    ('The model may work.', '模型有5层。', False),
    ('28.4 BLEU.', '29.4 BLEU。', False),
    ('4.5 million pairs.', '4500万对。', False),
    ('We used 8 GPUs.', '我们使用GPU。', False),
])
def test_numeric_translation_normalizes_units_without_inventing_values(source, translated, valid):
    if valid:
        check_numbers(source, translated, 'unit')
    else:
        with pytest.raises(PipelineError, match='翻译结果校验失败'):
            check_numbers(source, translated, 'unit')


def test_code_formula_and_markup_never_enter_model_payload(tmp_path, monkeypatch):
    client, _, bundle = api(tmp_path)
    _, calls = gateway(monkeypatch)
    response = client.post(f'/api/v1/papers/{bundle["paper_meta"]["id"]}/translate', json={'scope':'full'})
    assert response.status_code == 200
    payload = json.dumps([c['items'] for c in calls])
    assert '__SGKEEP_' not in payload
    assert 'print(' not in payload and '$x_1 + x_2$' not in payload
    assert r'\\frac' not in payload and '| --- |' not in payload


def test_arbitrary_prose_suggestion_does_not_become_a_mandatory_term(tmp_path, monkeypatch):
    client, _, bundle = api(tmp_path)
    def suggest(value, count):
        value['terminology'] = [{'source':'encoder and decoder','target':'编码器'}]
    gateway(monkeypatch, suggest)
    response = client.post(f'/api/v1/papers/{bundle["paper_meta"]["id"]}/translate', json={'scope':'abstract'})
    assert response.status_code == 200
    assert 'encoder and decoder' not in response.json()['metadata']['terminology']


@pytest.mark.real_model
def test_live_translation_uses_real_model_with_stored_chunk(tmp_path, request):
    client, _, bundle = api(tmp_path)
    response = client.post(f'/api/v1/papers/{bundle["paper_meta"]["id"]}/translate', json={'scope': 'abstract', 'target': 'zh'})
    assert response.status_code == 200
    value = response.json()
    assert len(value['segments']) == 1 and '12' in value['segments'][0]['translated_text']
    assert '编码器' in value['segments'][0]['translated_text'] and '解码器' in value['segments'][0]['translated_text']
    request.node.user_properties.extend(('translation_' + k, str(v)) for k, v in value['metadata']['model_calls'][-1].items())

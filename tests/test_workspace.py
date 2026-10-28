import copy
import hashlib
import json

from fastapi.testclient import TestClient
import pytest

from scholar_graph.api import create_app
from test_validation_status import example_bundle


@pytest.fixture
def workspace(tmp_path):
    app = create_app(data_dir=tmp_path)
    bundle = example_bundle()
    app.state.repository.store.paper(bundle)
    return TestClient(app), app, bundle


def publication_digest(root):
    return {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest() for p in root.rglob('*.json')}


def test_corrections_and_trash_are_persistent_without_changing_originals(workspace):
    client, app, bundle = workspace
    pid = bundle['paper_meta']['id']
    path = '/api/v2/papers/' + pid
    before = publication_digest(app.state.repository.root / 'papers')
    patched = client.patch(path, json={'title': '人工核对的标题', 'authors': ['原文作者']})
    assert patched.status_code == 200
    assert patched.json()['paper']['title'] == '人工核对的标题'
    assert client.get('/api/v1/papers/' + pid).json() == bundle['paper_meta']
    assert client.delete(path).json()['archived'] is True
    assert client.get('/api/v2/papers').json()['total'] == 0
    assert client.get('/api/v2/papers?archived=true').json()['total'] == 1
    fresh = TestClient(create_app(data_dir=app.state.repository.root))
    assert fresh.post(path + '/restore').json()['archived'] is False
    assert fresh.get(path).json()['paper']['title'] == '人工核对的标题'
    assert publication_digest(app.state.repository.root / 'papers') == before


@pytest.mark.parametrize('patch', [{'id': 'another'}, {'file_hash': 'bad'}, {'page_count': 0}, {'authors': None}, {'year': 0}])
def test_invalid_or_identity_mutations_are_rejected(workspace, patch):
    client, _, bundle = workspace
    response = client.patch('/api/v2/papers/' + bundle['paper_meta']['id'], json=patch)
    assert response.status_code == 422


def test_reading_reaches_beyond_two_thousand_chunks(tmp_path):
    app = create_app(data_dir=tmp_path)
    bundle = example_bundle()
    bundle['paper_meta']['page_count'] = 541
    prototype = bundle['chunks'][0]
    bundle['chunks'] = [{**prototype, 'chunk_id': f'chunk-{i}', 'page_number': min(541, i // 5 + 1)} for i in range(2705)]
    bundle['reference_entries'] = []
    bundle['citation_links'] = []
    app.state.repository.store.paper(bundle)
    response = TestClient(app).get('/api/v2/papers/' + bundle['paper_meta']['id'] + '/reading?physical_page=541')
    assert response.status_code == 200
    assert response.json()['total_chunks'] == 2705
    assert len(response.json()['chunks']) == 5
    assert all(c['page_number'] == 541 for c in response.json()['chunks'])
    compact = TestClient(app).get('/api/v2/papers/' + bundle['paper_meta']['id'] + '/reading?physical_page=541&include_navigation=false')
    assert compact.status_code == 200
    assert compact.json()['chunks'] == response.json()['chunks']
    assert compact.json()['total_chunks'] == 2705
    for field in ('outline','references','citation_links','bibliography_locations'):
        assert not compact.json()[field]


def test_selection_from_wrong_page_never_calls_model(workspace, monkeypatch):
    client, _, bundle = workspace
    def forbidden(*args, **kwargs):
        raise AssertionError('Unproven selection must not reach a model')
    monkeypatch.setattr('scholar_graph.workspace_routes.Translator.translate', forbidden)
    response = client.post('/api/v2/papers/' + bundle['paper_meta']['id'] + '/translate-selection',
                           json={'text': 'this does not occur in the source', 'page_number': 1})
    assert response.status_code == 422


def test_sessions_keep_scope_and_survive_restart(workspace):
    client, app, bundle = workspace
    pid = bundle['paper_meta']['id']
    assert client.post('/api/v2/sessions', json={'paper_ids': [pid, pid]}).status_code == 422
    response = client.post('/api/v2/sessions', json={'paper_ids': [pid]})
    assert response.status_code == 201
    session = response.json()
    app.state.workspace.append_message(session['id'], {'question': '上一个问题', 'status': 'cancelled'})
    fresh = TestClient(create_app(data_dir=app.state.repository.root))
    saved = fresh.get('/api/v2/sessions/' + session['id']).json()
    assert saved['paper_ids'] == [pid]
    assert saved['messages'][0]['status'] == 'cancelled'


def test_system_does_not_expose_credentials(workspace, monkeypatch):
    monkeypatch.setenv('DEEPSEEK_API_KEY', 'private-test-value')
    monkeypatch.setenv('DEEPSEEK_MODEL', 'test-model')
    result = workspace[0].get('/api/v2/system')
    assert result.json()['model_configured'] is True
    assert 'private-test-value' not in result.text


def test_arxiv_year_is_submission_year_without_rewriting_original(workspace):
    from scholar_graph.workspace import arxiv_submission_year
    assert arxiv_submission_year('1706.03762v7') == 2017
    assert arxiv_submission_year('0703.0001') is None
    assert arxiv_submission_year('1713.03762') is None
    assert arxiv_submission_year('9912.03762') is None
    client, app, bundle = workspace
    bundle['paper_meta'].update(arxiv_id='1706.03762v7', year=None)
    fresh = create_app(data_dir=app.state.repository.root / 'year-case')
    fresh.state.repository.store.paper(bundle)
    view = fresh.state.workspace.paper(bundle['paper_meta']['id'])
    assert view['paper']['year'] == 2017 and view['original']['year'] is None
    assert view['year_source'] == 'arxiv_submission_identifier'


def test_author_mapping_order_and_email_are_checked_without_editing_frozen_data(workspace):
    client, app, bundle = workspace; pid = bundle['paper_meta']['id']; names = bundle['paper_meta']['authors']
    if not names:
        client.patch('/api/v2/papers/'+pid, json={'authors':['Source Author']}); names=['Source Author']
    body = {'profiles':[{'name':name,'institutions':['Manual Institution'],'emails':['author@example.org']} for name in names], 'note':'依据原文手工补齐'}
    before = publication_digest(app.state.repository.root/'papers')
    assert client.patch('/api/v2/papers/'+pid+'/author-profiles', json=body).status_code == 200
    assert app.state.workspace.paper(pid)['author_profiles'][0]['source']=='user_author_mapping'
    assert publication_digest(app.state.repository.root/'papers')==before
    body['profiles'][0]['name']='Wrong Order'
    assert client.patch('/api/v2/papers/'+pid+'/author-profiles',json=body).status_code==422


def test_abstract_note_is_removed_without_trimming_scientific_asterisks():
    from scholar_graph.grobid import clean_abstract
    assert clean_abstract('Scientific result.* Equal contribution. Author notes.')=='Scientific result.'
    assert clean_abstract('We define x*y and discuss the model.')=='We define x*y and discuss the model.'

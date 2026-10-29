"""Actual input-count and chronological-publication boundaries, independent of model quality."""
import copy
import pytest
from fastapi.testclient import TestClient
from scholar_graph.api import create_app
from scholar_graph.errors import PipelineError
from scholar_graph.future_evidence import checked_comparison,future_sources
from test_validation_status import example_bundle
from scholar_graph.reference_identity import parse_reference
from scholar_graph.graph_service import build_graph,validate_graph
from scholar_graph.validation import ContractGate
from graph_samples import graph_bundles

def test_partial_multipart_file_count_never_becomes_successful_smaller_batch(tmp_path):
    app=create_app(data_dir=tmp_path);client=TestClient(app)
    response=client.post('/api/v2/uploads',data={'file_count':'20'},files=[('files',('first.pdf',b'%PDF-incomplete','application/pdf'))])
    assert response.status_code==422 and '文件数' in response.json()['message']
    assert client.get('/api/v2/tasks').json()==[]
    assert not list((tmp_path/'.task-inputs').glob('*'))

@pytest.mark.parametrize('count',['wrong','0','21','-1'])
def test_invalid_declared_upload_count_rejected_before_task(count,tmp_path):
    c=TestClient(create_app(data_dir=tmp_path))
    assert c.post('/api/v2/uploads',data={'file_count':count},files={'files':('x.pdf',b'x','application/pdf')}).status_code==422
    assert c.get('/api/v2/tasks').json()==[]

@pytest.mark.parametrize('year,expected',[(2026,'exclude'),(2017,'uncertain'),(2016,'uncertain'),(None,'uncertain')])
def test_only_strictly_later_real_quote_can_exclude_a_direction(year,expected):
    paper={'id':'later','year':year,'abstract':'We apply local window attention to long sequences.'}
    value={'decision':'exclude','reason':'后续摘要明确尝试局部注意力。','matches':[{'candidate_id':'later','quote':paper['abstract']}]}
    assert checked_comparison(value,[paper],2017,'局部注意力')['decision']==expected
    assert checked_comparison(value,[paper],None,'局部注意力')['decision']=='uncertain'

def test_old_goal_is_not_recommended_when_reason_says_already_attempted():
    p={'id':'new','year':2026,'abstract':'We apply local attention; efficiency remains challenging.'}
    v={'decision':'include','reason':'已有工作尝试该方向，不宜当作未探索问题推荐。','matches':[{'candidate_id':'new','quote':p['abstract']}]}
    assert checked_comparison(v,[p],2017,'局部注意力')['decision']=='uncertain'
    v.update(remaining_topic='优化局部注意力在特定稀疏模式下的效率',reason='摘要明确说明效率仍具挑战，仅作有边界的候选。')
    assert checked_comparison(v,[p],2017,'局部注意力')['remaining_topic']==v['remaining_topic']

def test_invented_quote_or_unselected_candidate_never_published():
    p={'id':'new','year':2026,'abstract':'A genuine public abstract.'}
    for match in [{'candidate_id':'new','quote':'Invented finding'},{'candidate_id':'unknown','quote':p['abstract']}]:
        with pytest.raises(PipelineError):checked_comparison({'decision':'exclude','reason':'x','matches':[match]},[p],2017,'topic')

def test_future_sources_do_not_drop_the_last_fifteen_selected_papers():
    bundles=[]
    for i in range(20):
        b=example_bundle();pid=f'paper-{i}';b['paper_meta']['id']=pid
        for chunk in b['chunks']:chunk.update(paper_id=pid,chunk_id=f'{pid}-chunk',text='Future work: We plan to investigate anchored long context reasoning further.')
        bundles.append(b)
    rows=future_sources(bundles)
    assert {r['paper_id'] for r in rows}=={b['paper_meta']['id'] for b in bundles}
    assert len(rows)<=60

def test_attempted_original_goal_is_excluded_even_if_model_suggests_a_narrower_gap():
    p={'id':'new','year':2026,'abstract':'We apply local attention; efficiency remains challenging.'}
    value={'attempted':True,'decision':'include','reason':'已有尝试；可以继续改善效率。','remaining_topic':'改善特定场景的效率',
        'matches':[{'candidate_id':'new','quote':p['abstract']}]}
    result=checked_comparison(value,[p],2017,'局部注意力')
    assert result['decision']=='exclude' and result['remaining_candidate']['decision']=='uncertain'

@pytest.mark.parametrize('raw,title',[
    ('Smith, A., Jones, M.-W., and Chen, B. A grounded reference parser. Venue, 2020.','A grounded reference parser'),
    ('Smith, A., and Chen, B. (2020). A grounded reference parser. Venue.','A grounded reference parser'),
    ('A. Smith, M.-A. Jones, et al. A grounded reference parser. Venue, 2020.','A grounded reference parser'),
    ('Alice Smith and Bob Chen. A grounded reference parser, 2020, arXiv:2001.12345.','A grounded reference parser')])
def test_real_bibliography_formats_keep_the_title_out_of_the_author_list(raw,title):
    assert parse_reference(raw)['title']==title

def test_v2_bibliography_evidence_is_explicit_and_v1_does_not_invent_a_body_anchor():
    a,b=graph_bundles()[:2];a['citation_links']=[]
    bib={**a['chunks'][0],'chunk_id':'original-bib','section_path':['References'],'heading_1':'References',
        'heading_2':None,'heading_3':None,'text':'[1] Demo Author. '+b['paper_meta']['title']+'. 2020.'}
    a['chunks'].append(bib)
    gate=ContractGate();old=build_graph([a,b],gate)
    assert old['edges'][0]['status']=='unverified'
    new=build_graph([a,b],gate,bibliography_fallback=True)
    assert new['edges'][0]['status']=='verified' and new['edges'][0]['anchor']['chunk_id']=='original-bib'
    proof=new['diagnostics']['edge_evidence'][0]
    assert proof['evidence_kind']=='bibliography_identity' and proof['body_quote'] is None
    validate_graph(new,[a,b],gate,bibliography_fallback=True)

def test_graph_cache_never_returns_a_callers_mutation_or_stale_input():
    bundles=graph_bundles();gate=ContractGate();first=build_graph(bundles,gate)
    first['nodes'][0]['pagerank']=999
    next_value=build_graph(bundles,gate);assert next_value['nodes'][0]['pagerank']!=999
    validate_graph(next_value,bundles,gate)
    bundles[0]['paper_meta']['title']='Corrected source title'
    changed=build_graph(bundles,gate)
    assert any(n['title']=='Corrected source title' for n in changed['nodes'])

def test_twenty_paper_bundle_cache_retains_inputs_but_applies_new_corrections(tmp_path,monkeypatch):
    import json
    app=create_app(data_dir=tmp_path);workspace=app.state.workspace;repo=app.state.repository;ids=[]
    for i in range(20):
        b=example_bundle();pid=f'paper-{i}';ids.append(pid);b['paper_meta']['id']=pid
        for j,c in enumerate(b['chunks']):c.update(paper_id=pid,chunk_id=f'{pid}-c{j}')
        b['reference_entries']=[];b['citation_links']=[];repo.store.paper(b)
    original=repo.paper;loads=[]
    def counted(pid):loads.append(pid);return original(pid)
    monkeypatch.setattr(repo,'paper',counted)
    for pid in ids:workspace.bundle(pid)
    for pid in ids:workspace.bundle(pid)
    assert len(loads)==20
    workspace.update(ids[-1],{'title':'Saved user correction'})
    assert workspace.bundle(ids[-1])['paper_meta']['title']=='Saved user correction'
    path=tmp_path/'papers'/ids[-1]/'chunks.json';chunks=json.loads(path.read_text());chunks[0]['page_number']=0;path.write_text(json.dumps(chunks))
    with pytest.raises(PipelineError):workspace.bundle(ids[-1])

def test_compact_graph_keeps_rank_and_edges_and_never_erases_full_evidence(tmp_path):
    app=create_app(data_dir=tmp_path);c=TestClient(app);bundles=graph_bundles()
    for b in bundles:app.state.repository.store.paper(b)
    ids=[b['paper_meta']['id'] for b in bundles]
    compact=c.post('/api/v2/graph/rebuild',json={'paper_ids':ids,'compact':True});assert compact.status_code==200
    full=c.get('/api/v2/graph',params=[('paper_ids',pid) for pid in ids]);assert full.status_code==200
    a,b=compact.json(),full.json()
    assert a['nodes']==b['nodes'] and a['edges']==b['edges'] and a['layers']==b['layers']
    assert a['diagnostics']['reference_resolutions']==[] and b['diagnostics']['reference_resolutions']
    assert any(p['body_quote'] for p in b['diagnostics']['edge_evidence'])

def test_table_label_title_is_recovered_but_saved_user_title_is_preserved(tmp_path):
    from scholar_graph.front_matter import local_front_matter,apply_local_front_matter
    b=example_bundle();b['paper_meta']['title']='GPQA-Diamond';base=b['chunks'][0]
    def row(id,text,bbox,section=None):return {**base,'chunk_id':id,'text':text,'bbox':bbox,'section_path':[section] if section else [],'heading_1':section,'heading_2':None,'heading_3':None}
    b['chunks']=[row('cover','Actual Grounded Model Technical Report',[.2,.1,.8,.15]),row('abstract','Abstract',[.4,.3,.6,.32],'Abstract'),row('chart','GPQA-Diamond is a label inside a comparison table.',[.1,.6,.9,.8],'Abstract')]
    b['reference_entries']=[];b['citation_links']=[]
    assert local_front_matter(b)[0]['title']=='Actual Grounded Model Technical Report'
    app=create_app(data_dir=tmp_path);app.state.repository.store.paper(b);w=app.state.workspace
    w.update(b['paper_meta']['id'],{'title':'Explicit user title'})
    apply_local_front_matter(w,b['paper_meta']['id'])
    assert w.paper(b['paper_meta']['id'])['paper']['title']=='Explicit user title'


def test_public_query_failure_preserves_local_and_prior_successful_evidence(monkeypatch):
    from scholar_graph import workspace_future as future
    local={'id':'local','year':2024};remote={'id':'remote','year':2026}
    monkeypatch.setattr(future,'local_candidates',lambda *args:[local])
    class Search:
        def search(self,query,limit):
            if 'second' in query:raise PipelineError('UPSTREAM_ERROR','Public service unavailable')
            return [remote]
    papers,queries,errors=future.search_candidates(Search(),[], 'source',2017,['first query','second query'])
    assert {p['id'] for p in papers}=={'local','remote'}
    assert queries[0]['returned_ids']==['remote'] and queries[1]['error']['error_code']=='UPSTREAM_ERROR'
    assert len(errors)==1


def test_later_paper_bibliography_does_not_become_a_dated_research_attempt():
    from scholar_graph.future_evidence import local_candidates
    b=example_bundle();b['paper_meta'].update(year=2024,abstract=None)
    c=b['chunks'][0];b['chunks']=[{**c,'text':'Alice Smith. Local attention for very long sequence modeling. 2019.',
        'section_path':['References'],'heading_1':'References','heading_2':None,'heading_3':None}]
    assert local_candidates([b],'other',2017,['local attention'])==[]

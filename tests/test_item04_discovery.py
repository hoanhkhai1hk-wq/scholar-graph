"""Deterministic controls for discovery fixes; real network/browser evidence is separate."""
import copy
import time
from types import SimpleNamespace

from fastapi.testclient import TestClient
from graph_samples import graph_bundles
from scholar_graph.api import create_app
from scholar_graph.author_metadata import source_author_profiles
from scholar_graph.reference_importance import citation_context, rank_references
from scholar_graph.tracking import TrackingService
from scholar_graph.workspace_recommendations import code_links, workbench_recommendations
from scholar_graph.normalize import reference_entries, citation_links
from scholar_graph.reference_acquisition import fetch_reference


def test_context_ranking_promotes_adopted_method_over_background_frequency():
    bundle=graph_bundles()[0]; ref=bundle['reference_entries'][0]
    other={**ref,'ref_id':'method-ref','number':2,'title':'Layer normalization'}
    original=bundle['chunks'][0]
    background=[{**original,'chunk_id':f'background-{i}','text':'Related prior work [1].','section_path':['Background']} for i in range(5)]
    method={**original,'chunk_id':'method','text':'We use layer normalization [2].','section_path':['3 Architecture']}
    bundle['chunks']=background+[method];bundle['reference_entries'].append(other)
    bundle['citation_links']=[{**bundle['citation_links'][0],'chunk_id':c['chunk_id']} for c in background]
    bundle['citation_links'].append({**bundle['citation_links'][0],'chunk_id':'method','ref_id':'method-ref','citation_number':2})
    ranked=rank_references(bundle)
    assert ranked[0]['reference']['number']==2
    assert ranked[0]['content_contexts'][0]['anchor']['chunk_id']=='method'
    assert ranked[0]['importance']==1 and ranked[1]['importance']==5
    bundle['citation_links'].append(bundle['citation_links'][0])
    assert rank_references(bundle)==ranked  # Repeated link records cannot inflate scores.


def test_context_marker_matches_number_not_substring_and_groups_ranges():
    chunk={'text':'Background [11]. We use this method [1, 3–5]. Final words.'}
    quote,found=citation_context(chunk,1)
    assert found and '[11]' not in quote and '[1, 3–5]' in quote
    assert citation_context(chunk,4)==(quote,True)
    assert citation_context(chunk,9)[1] is False


def test_post_bibliography_table_inline_marker_is_not_a_duplicate_entry():
    bundle=graph_bundles()[0];chunk=bundle['chunks'][0];pid=bundle['paper_meta']['id']
    refs={**chunk,'section_path':['References'],'text':'[15] Demo Author. Example Paper. In A Venue, 2020.'}
    caption={**refs,'chunk_id':'caption','text':'Table 11: Translation results from PBMT [15], our model and humans.'}
    result=reference_entries([refs,caption],pid)
    assert len(result)==1 and result[0]['number']==15
    assert citation_links([refs,caption],[])==[]


def test_tracking_task_network_failure_cannot_be_completed(tmp_path):
    app=create_app(data_dir=tmp_path)
    app.state.workspace_tracking.run=lambda **kwargs:{'status':'failed','failed_count':0,'errors':[{'message':'synthetic connection failure'}]}
    with TestClient(app) as client:
        task=client.post('/api/v2/tracking/tasks',json={'paper_ids':['seed']}).json()
        for _ in range(100):
            task=client.get('/api/v2/tasks/'+task['id']).json()
            if task['status'] not in ['queued','running']:break
            time.sleep(.01)
        assert task['status']=='failed' and task['result']['failed_count']==1


def test_new_download_budget_is_not_consumed_by_known_arxiv(tmp_path):
    app=create_app(data_dir=tmp_path);known=graph_bundles()[0]
    known['paper_meta'].update(arxiv_id='2601.00001v1',title='Synthetic Graph Study')
    app.state.repository.store.paper(known)
    old=copy.deepcopy(known['paper_meta'])
    new={**old,'id':'arxiv-2601.00002v1','arxiv_id':'2601.00002v1','title':'Synthetic Graph Study Extended'}
    calls=[]
    def fetch(metadata):
        calls.append(metadata['arxiv_id'])
        return {'succeeded':True,'already_present':metadata['arxiv_id']==old['arxiv_id'],'paper':metadata,'error':None}
    fetcher=SimpleNamespace(client=SimpleNamespace(search=lambda query,limit:[old,new]),fetch_metadata=fetch)
    result=TrackingService(app.state.repository,fetcher,read_only_sources=True).run(paper_ids=[old['id']],max_imports=1,max_candidates=2)
    assert result['status']=='completed',result
    assert result['imported_count']==1 and result['duplicate_count']==1 and len(calls)==2
    assert result['candidates'][0]['arxiv_id']==new['arxiv_id']


def test_grouped_email_does_not_hide_shared_institution():
    original=graph_bundles()[0]['chunks'][0]
    def chunk(cid,text,y):return {**original,'chunk_id':cid,'text':text,'bbox':[.2,y,.8,y+.014],'page_number':1,'type':'text'}
    bundle={'chunks':[chunk('a','Demo Author',.15),chunk('b','Other Person',.15),chunk('org','Synthetic Research Institute',.18),
        chunk('contact','{demoauthor,otherperson}@research.example',.20),chunk('abs','Abstract',.26)],'paper_meta':{'title':'Synthetic title'}}
    profiles=source_author_profiles(bundle,['Demo Author','Other Person'])
    assert all(p['institutions']==['Synthetic Research Institute'] for p in profiles)
    assert all(p['emails']==[] for p in profiles)  # Group order alone is not an email/name mapping.


def test_code_signal_requires_own_body_not_bibliography():
    bundle=graph_bundles()[0];c=bundle['chunks'][0]
    bundle['chunks']=[{**c,'text':'See https://github.com/other/repo','section_path':['References']}]
    assert code_links(bundle)==[]
    bundle['chunks'].append({**c,'text':'Code: https://github.com/demo/own/tree/main`','section_path':['Implementation']})
    assert code_links(bundle)[0]['url']=='https://github.com/demo/own'


def test_v2_reasons_and_feedback_are_persistent_and_code_is_ten_points(tmp_path):
    app=create_app(data_dir=tmp_path)
    for b in graph_bundles():app.state.repository.store.paper(b)
    base=workbench_recommendations(app.state.workspace,'paper-graph-a',2026,votes=[])
    assert len(base)==3 and all('Synthetic Graph Study A' in i['relationship_reason'] for i in base)
    target=base[-1]['paper']['id']
    with TestClient(app) as client:
        for vote in ['like','dislike']:
            event=client.post('/api/v2/recommendations/feedback',json={'paper_id':target,'seed_paper_id':'paper-graph-a','vote':vote})
            assert event.status_code==200
        ranked=client.get('/api/v2/recommendations',params={'paper_id':'paper-graph-a'}).json()
        assert next(v for v in ranked['votes'] if v['paper_id']==target)['vote']==-1
    fresh=TestClient(create_app(data_dir=tmp_path))
    assert fresh.get('/api/v2/recommendations',params={'paper_id':'paper-graph-a'}).json()['votes']==ranked['votes']


def test_code_bonus_changes_score_by_exactly_ten_with_same_other_signals(tmp_path):
    apps=[]
    for code in [False,True]:
        app=create_app(data_dir=tmp_path/str(code))
        bundles=graph_bundles()
        if code:bundles[1]['chunks'][0]['text']+=' Code https://github.com/demo/repro'
        for b in bundles:app.state.repository.store.paper(b)
        apps.append(workbench_recommendations(app.state.workspace,'paper-graph-a',2026,votes=[]))
    before=next(r for r in apps[0] if r['paper']['id']=='paper-graph-b')
    after=next(r for r in apps[1] if r['paper']['id']=='paper-graph-b')
    assert abs(after['score']-before['score']-10)<1e-10
    assert after['code_priority_bonus']==10 and after['signals']['github_link']==1
    assert 'github_link' not in after['missing_signals']


def test_abbreviated_reference_requires_unique_author_set_and_year():
    failure={'succeeded':False,'error':{'error_code':'PAPER_NOT_FOUND'}}
    ref={'title':'A synthetic decomposable attention model','authors':['Alice Smith','Bob Lee'],'year':2020}
    paper={'title':ref['title']+' for example inference','authors':ref['authors'],'year':2020}
    fetcher=SimpleNamespace(fetch=lambda **kwargs:failure,client=SimpleNamespace(search=lambda *args,**kwargs:[paper]),fetch_metadata=lambda p:{'succeeded':True,'paper':p})
    assert fetch_reference(fetcher,ref)['reference_resolution']['resolved_title']==paper['title']
    for changes in [{'year':2021},{'authors':['Other Author']},{'title':'Different unrelated paper'}]:
        fetcher.client.search=lambda *args,**kwargs:[{**paper,**changes}]
        assert fetch_reference(fetcher,ref)==failure
    fetcher.client.search=lambda *args,**kwargs:[paper,paper]
    assert fetch_reference(fetcher,ref)==failure


def test_base_cache_invalidates_metadata_and_never_reuses_another_profiles_votes(tmp_path):
    app=create_app(data_dir=tmp_path)
    for b in graph_bundles():app.state.repository.store.paper(b)
    workspace=app.state.workspace;diag={}
    base=workbench_recommendations(workspace,'paper-graph-a',2026,votes=[],diagnostics=diag)
    assert diag['base_cache_hit'] is False
    d2={};warm=workbench_recommendations(workspace,'paper-graph-a',2026,votes=[],diagnostics=d2)
    assert warm==base and d2['base_cache_hit'] is True
    liked=workbench_recommendations(workspace,'paper-graph-a',2026,votes=[{'paper_id':'paper-graph-d','vote':1}])
    assert liked!=base
    assert workbench_recommendations(workspace,'paper-graph-a',2026,votes=[])==base
    workspace.update('paper-graph-d',{'title':'A changed topic entirely'})
    d3={};workbench_recommendations(workspace,'paper-graph-a',2026,votes=[],diagnostics=d3)
    assert d3['base_cache_hit'] is False and d3['library_signature']!=diag['library_signature']

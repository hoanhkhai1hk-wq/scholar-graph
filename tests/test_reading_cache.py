"""Reader acceleration must never hide editable sidecars or changed publications."""
import copy
import json
from fastapi.testclient import TestClient
from scholar_graph.api import create_app
from test_validation_status import example_bundle

def setup(tmp_path):
    app=create_app(data_dir=tmp_path)
    bundle=example_bundle();app.state.repository.store.paper(bundle)
    return app,app.state.workspace,bundle

def test_hot_pages_reuse_validated_material_but_remain_page_scoped(tmp_path,monkeypatch):
    app,w,b=setup(tmp_path);pid=b['paper_meta']['id'];first=w.reading(pid)
    def forbidden(*args,**kwargs):raise AssertionError('Hot page must not reload the whole bundle')
    monkeypatch.setattr(w,'bundle',forbidden)
    hot=w.reading(pid,1,False)
    assert hot['chunks']==first['chunks']
    assert hot['total_chunks']==len(b['chunks'])
    assert hot['outline']==[] and hot['references']==[]

def test_metadata_change_invalidates_same_instance_and_external_connection(tmp_path):
    app,w,b=setup(tmp_path);pid=b['paper_meta']['id'];w.reading(pid)
    other=create_app(data_dir=tmp_path).state.workspace
    other.update(pid,{'title':'已核对的标题'})
    assert w.reading(pid)['paper']['title']=='已核对的标题'

def test_new_chat_or_task_does_not_discard_book_material(tmp_path,monkeypatch):
    app,w,b=setup(tmp_path);pid=b['paper_meta']['id'];w.reading(pid)
    w.put('session','new-session',{'id':'new-session','paper_ids':[pid]})
    monkeypatch.setattr(w,'bundle',lambda *args: (_ for _ in ()).throw(AssertionError('unrelated write invalidated cache')))
    assert w.reading(pid)['total_chunks']==len(b['chunks'])

def test_classification_and_reference_enrichment_invalidate_navigation(tmp_path):
    app,w,b=setup(tmp_path);pid=b['paper_meta']['id'];first=w.reading(pid)
    target=b['chunks'][0]
    w.put('classification','manual-edit',{'paper_id':pid,'chunk_id':target['chunk_id'],'type':'text','section_path':['1 Corrected heading']})
    updated=w.reading(pid)
    assert updated['chunks'][0]['section_path']==['1 Corrected heading']
    assert any(x['section_path']==['1 Corrected heading'] for x in updated['outline'])
    w.put('enrichment',pid,{'references':[],'citation_links':[]})
    assert w.reading(pid)['references']==[] and w.reading(pid)['citation_links']==[]

def test_layout_and_code_sidecar_changes_invalidate_cache(tmp_path):
    app,w,b=setup(tmp_path);pid=b['paper_meta']['id'];w.reading(pid)
    original=w._reading_cache[pid]
    w.put('layout_page',pid+'-p0001',{'paper_id':pid,'page_number':1,'regions':[]})
    w.reading(pid);assert w._reading_cache[pid] is not original
    original=w._reading_cache[pid];w.put('code_layout',pid,{'version':'fixture-other-version'})
    w.reading(pid);assert w._reading_cache[pid] is not original

def test_changed_frozen_file_is_revalidated_and_invalid_page_stays_error(tmp_path):
    app,w,b=setup(tmp_path);pid=b['paper_meta']['id'];w.reading(pid)
    p=tmp_path/'papers'/pid/'chunks.json';chunks=json.loads(p.read_text(encoding='utf8'));chunks[0]['text']='Source text updated on disk.';p.write_text(json.dumps(chunks),encoding='utf8')
    assert w.reading(pid)['chunks'][0]['text']=='Source text updated on disk.'
    response=TestClient(app).get('/api/v2/papers/'+pid+'/reading?physical_page=999')
    assert response.status_code==422

def test_new_parse_batch_appears_without_restarting_reader(tmp_path):
    app=create_app(data_dir=tmp_path);w=app.state.workspace;b=example_bundle()
    b['reference_entries']=[];b['citation_links']=[]
    one=copy.deepcopy(b);one['chunks']=[b['chunks'][0]]
    app.state.repository.store.partial_batch(one,1)
    assert w.reading(b['paper_meta']['id'])['total_chunks']==1
    two=copy.deepcopy(one);two['chunks'][0]['chunk_id']='new-later-page-chunk'
    app.state.repository.store.partial_batch(two,2)
    assert w.reading(b['paper_meta']['id'])['total_chunks']==2

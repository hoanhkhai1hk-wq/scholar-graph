"""Protocol safety tests; actual BGE timings live in item08, not these mocks."""
from types import SimpleNamespace
import math
import pytest
from scholar_graph.vector_search import BgeChromaSearch
from scholar_graph.retrieval import VectorUnavailable
from scholar_graph.rerank_worker import WorkerUnavailable, ResidentVector

def service(tmp_path):
    python=tmp_path/'python';python.touch();model=tmp_path/'model';model.mkdir();(model/'config.json').write_text('{}')
    return BgeChromaSearch(python,model,tmp_path/'index',resident=True)

def test_resident_keeps_current_source_ids_and_reports_startup(tmp_path,monkeypatch):
    s=service(tmp_path);seen=[]
    def score(payload,budget):
        seen.append(payload)
        return {'dense':{'a':.8},'sparse':{'a':.5}}, {'cold_start':False,'startup':{'ready':True}}
    monkeypatch.setattr('scholar_graph.vector_search.resident_vector_worker',lambda *args:SimpleNamespace(score=score))
    assert s.search([{'chunk_id':'a'}],'question')
    assert seen[0]['chunks']==[{'chunk_id':'a'}] and seen[0]['index_path']==str(s.index_path)
    assert s.last_evidence['residency']['cold_start'] is False

@pytest.mark.parametrize('bad',['stale','nonfinite','timeout'])
def test_resident_failure_never_becomes_vector_success(tmp_path,monkeypatch,bad):
    s=service(tmp_path)
    def score(*args):
        if bad=='timeout':raise WorkerUnavailable('LOCAL_VECTOR_TIMEOUT')
        return {'dense':{'x' if bad=='stale' else 'a':float('nan') if bad=='nonfinite' else .5},'sparse':{'a':1}},{}
    monkeypatch.setattr('scholar_graph.vector_search.resident_vector_worker',lambda *args:SimpleNamespace(score=score))
    with pytest.raises(VectorUnavailable):s.search([{'chunk_id':'a'}],'question')
    assert s.last_evidence is None

def test_vector_worker_uses_vector_errors_and_is_distinct_from_reranker():
    assert ResidentVector.mode=='vector'
    assert ResidentVector.error_prefix=='LOCAL_VECTOR'
    assert ResidentVector.inference_timeout=='LOCAL_VECTOR_TIMEOUT'

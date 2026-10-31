"""Timeout classification and in-flight progress, with explicitly mocked transport."""
import json
import httpx
import pytest
from scholar_graph.arxiv_fetch import ArxivClient
from scholar_graph.errors import PipelineError
from scholar_graph.tracking_state import TrackingState
from scholar_graph.validation import ContractGate
from test_arxiv_fetch import ATOM
from test_tracking import prepared


@pytest.mark.parametrize('kind,reason', [(httpx.ReadTimeout, 'UPSTREAM_TIMEOUT'),
                                       (httpx.ConnectError, 'UPSTREAM_CONNECTION_FAILED')])
def test_request_error_reports_reason_without_raw_transport_secrets(kind, reason):
    def handle(request):
        raise kind('private-proxy-password-must-not-leak', request=request)
    client=ArxivClient(ContractGate(),transport=httpx.MockTransport(handle),interval=0)
    with pytest.raises(PipelineError) as caught:client.search('all:attention',1)
    envelope=caught.value.envelope()
    assert envelope['error_code']=='UPSTREAM_ERROR'
    assert envelope['details']['reason']==reason
    assert envelope['details']['exception_type']==kind.__name__
    assert envelope['details']['attempts']==1
    assert envelope['details']['timeout_seconds']==10
    assert 'private-proxy-password' not in json.dumps(envelope)


def test_search_timeout_does_not_shorten_pdf_download_read_timeout():
    calls=[]
    def handle(request):
        calls.append((request.url.path,request.extensions['timeout']))
        return httpx.Response(200,content=ATOM if request.url.path=='/api/query' else b'pdf-test')
    client=ArxivClient(ContractGate(),transport=httpx.MockTransport(handle),interval=0)
    client.search('all:attention',1)
    client.pdf({'arxiv_id':'1706.03762'})
    assert calls[0][1]['connect']==5 and calls[0][1]['read']==10
    assert calls[1][1]['read']==30


def test_progress_publishes_discoveries_before_all_queries_finish(tmp_path):
    api,app=prepared(tmp_path)
    real_format=ArxivClient(app.state.repository.gate,transport=httpx.MockTransport(
        lambda request:httpx.Response(200,content=ATOM.replace(b'Synthetic ScholarGraph Study',b'Synthetic Graph Study'))),interval=0)
    paper=real_format.metadata('Synthetic Graph Study');snapshots=[]
    def search(query,limit):
        snapshots.append(TrackingState(app.state.repository.root).latest())
        return [paper]
    app.state.arxiv_fetcher.client.search=search
    result=api.post('/api/v1/retrieval/tracking/run',json={'paper_ids':['paper-graph-a'],'max_imports':0}).json()
    assert len(snapshots)>=2
    assert snapshots[0]['phase']=='querying' and snapshots[0]['query_total_count']==len(snapshots)
    assert snapshots[1]['discovered_count']==1
    assert result['status']=='completed' and result['phase']=='finished'
    assert result['max_imports']==0 and result['imported_count']==0

"""Self-made PDF/TEI and simulated failures, not real GROBID acceptance."""
import copy
import json
from urllib.parse import unquote

import httpx
import pytest
from fastapi.testclient import TestClient

from scholar_graph.api import create_app
from scholar_graph.api_repository import ApiRepository
from scholar_graph.arxiv_fetch import ArxivFetcher,ArxivClient
from scholar_graph.grobid import GrobidClient
from scholar_graph.grobid_enrichment import DefaultGrobid,merge
from scholar_graph.validation import ContractGate
from sample_pdfs import make_pdf
from test_grobid_evidence import TEI
from test_validation_status import example_bundle
from test_arxiv_fetch import ATOM,TITLE


def configure(monkeypatch,outcome='ok'):
    calls=[]
    def handle(request):
        calls.append(request)
        if outcome=='timeout':raise httpx.ReadTimeout('synthetic-private-detail',request=request)
        if outcome=='unavailable':raise httpx.ConnectError('synthetic-private-detail',request=request)
        return httpx.Response(503 if outcome=='http' else 200,content=b'not XML' if outcome=='xml' else TEI)
    monkeypatch.setenv('SCHOLAR_GRAPH_GROBID_ENABLED','true')
    monkeypatch.setattr('scholar_graph.grobid_enrichment.GrobidClient',lambda url,**kw:
        GrobidClient(url,**kw,transport=httpx.MockTransport(handle)))
    # Complete synthetic native output, no engine worker/model called.
    native={'schema':'docvortex.middle','is_full_document':True,'pages':[
        {'page_idx':n,'blocks':[{'type':'text','content':[{'type':'text','content':'Synthetic evidence.'}]}]} for n in range(2)]}
    monkeypatch.setattr('scholar_graph.adapters.LocalEngines.text',lambda *a,**k:copy.deepcopy(native))
    return calls


def meta(response):
    return json.loads(unquote(response.headers['X-ScholarGraph-Parse-Meta']))


@pytest.mark.parametrize('outcome,method',[('ok','mineru+grobid'),('http','mineru-fallback'),
    ('timeout','mineru-fallback'),('unavailable','mineru-fallback'),('xml','mineru-fallback')])
def test_default_http_factory_fail_open_and_persistent_optional_metadata(tmp_path,monkeypatch,outcome,method):
    calls=configure(monkeypatch,outcome)
    client=TestClient(create_app(data_dir=tmp_path/'records'))
    pdf=make_pdf(tmp_path/'selfmade.pdf')
    response=client.post('/api/v1/papers',files={'file':('selfmade.pdf',pdf.read_bytes(),'application/pdf')},
        headers={'Origin':'http://localhost:3000'})
    assert response.status_code==201,response.text
    paper=response.json();ContractGate().record('PaperMeta',paper)
    trace=meta(response)
    assert trace['method']==method and trace['grobid_attempted']
    assert 'parse_metadata' not in paper and len(calls)==1
    if outcome!='ok':
        assert trace['fallback_reason'] and trace['grobid_error']['error_code']=='UPSTREAM_ERROR'
        assert 'synthetic-private-detail' not in json.dumps(trace)
    if outcome in ('timeout','unavailable'):
        assert trace['grobid_error']['details']['failure_kind']==outcome
    for path in ('','/parse-status'):
        got=client.get('/api/v1/papers/'+paper['id']+path)
        assert got.status_code==200 and meta(got)['method']==method
    assert client.get('/api/v1/papers/'+paper['id']+'/parse-status').json()['status']=='completed'
    assert 'X-ScholarGraph-Parse-Meta'.lower() in response.headers['access-control-expose-headers'].lower()
    # Immutable byte-identical replay reuses the saved method, without pretending a new call.
    replay=client.post('/api/v1/papers',files={'file':('renamed.pdf',pdf.read_bytes(),'application/pdf')})
    assert replay.json()==paper and meta(replay)['cache_hit'] and not meta(replay)['grobid_attempted']
    assert len(calls)==1


def test_disabled_mode_does_not_attempt_service(tmp_path,monkeypatch):
    calls=configure(monkeypatch)
    monkeypatch.setenv('SCHOLAR_GRAPH_GROBID_ENABLED','false')
    client=TestClient(create_app(data_dir=tmp_path/'records'))
    pdf=make_pdf(tmp_path/'selfmade.pdf')
    response=client.post('/api/v1/papers',files={'file':('selfmade.pdf',pdf.read_bytes())})
    assert response.status_code==201 and meta(response)['method']=='mineru' and not calls


@pytest.mark.parametrize('key,value',[('SCHOLAR_GRAPH_GROBID_ENABLED','bad'),
    ('SCHOLAR_GRAPH_GROBID_TIMEOUT','nan'),('GROBID_URL','http://user:secret@example.invalid')])
def test_invalid_optional_configuration_does_not_reject_upload(tmp_path,monkeypatch,key,value):
    configure(monkeypatch);monkeypatch.setenv(key,value)
    client=TestClient(create_app(data_dir=tmp_path/'records'));pdf=make_pdf(tmp_path/'selfmade.pdf')
    response=client.post('/api/v1/papers',files={'file':('selfmade.pdf',pdf.read_bytes())})
    assert response.status_code==201 and meta(response)['method']=='mineru-fallback'
    assert 'user:secret' not in json.dumps(meta(response))


def test_merge_protects_anchors_identity_local_doi_and_nonempty_values():
    local=example_bundle();local['paper_meta']['doi']='10.5555/known';remote=copy.deepcopy(local)
    remote['paper_meta'].update(title='Structured title',authors=['Grobid Author'],institutions=[],doi='10.5555/conflict')
    remote['reference_entries'][0].update(venue='Structured venue',title=local['reference_entries'][0]['title'])
    output,details=merge(local,remote,ContractGate())
    assert output['chunks']==local['chunks'] and output['paper_meta']['doi']==local['paper_meta']['doi']
    assert output['paper_meta']['institutions']==local['paper_meta']['institutions']
    assert output['reference_entries'][0]['venue']=='Structured venue'
    assert output['reference_entries'][0]['ref_id']==local['reference_entries'][0]['ref_id']
    assert all(link in output['citation_links'] for link in local['citation_links'])
    assert details['references_enriched']==1
    remote['reference_entries'][0]['title']='Unrelated written title'
    remote['reference_entries'][0]['doi']=None
    rejected,_=merge(local,remote,ContractGate())
    assert rejected['reference_entries']==local['reference_entries']


@pytest.mark.parametrize('kind',['mutated_chunk','invalid_schema','empty'])
def test_invalid_enrichment_rolls_back_whole_candidate(monkeypatch,kind):
    monkeypatch.setenv('SCHOLAR_GRAPH_GROBID_ENABLED','true')
    local=example_bundle();before=copy.deepcopy(local)
    class Client:
        def enrich(self,bundle,raw):
            if kind=='mutated_chunk':bundle['chunks'][0]['text']='Changed source evidence'
            elif kind=='invalid_schema':bundle['paper_meta']['title']=''
            return bundle
    monkeypatch.setattr('scholar_graph.grobid_enrichment.GrobidClient',lambda *a,**k:Client())
    result,trace=DefaultGrobid().apply(local,b'%PDF-test',ContractGate())
    assert result==before==local and trace['method']=='mineru-fallback'


def test_batch_and_default_arxiv_factory_share_optional_enrichment(tmp_path,monkeypatch):
    configure(monkeypatch)
    pdf=make_pdf(tmp_path/'selfmade.pdf').read_bytes()
    client=TestClient(create_app(data_dir=tmp_path/'batch'))
    batch=client.post('/api/v1/papers/batch',files=[('files',('selfmade.pdf',pdf,'application/pdf'))]).json()
    assert batch['succeeded_count']==1 and batch['succeeded'][0]['parse_metadata']['method']=='mineru+grobid'
    repository=ApiRepository(tmp_path/'fetch',ContractGate())
    upstream=ArxivClient(repository.gate,transport=httpx.MockTransport(lambda r:
        httpx.Response(200,content=ATOM.replace(b'<arxiv:affiliation>Synthetic Institute</arxiv:affiliation>',b'') if r.url.path=='/api/query' else pdf)),interval=0)
    result=ArxivFetcher(repository,client=upstream).fetch(title=TITLE)
    assert result['succeeded'] and result['parse_metadata']['method']=='mineru+grobid'
    assert result['paper']['title']==TITLE and result['paper']['authors']==['Demo Author']
    again=ArxivFetcher(repository,client=upstream).fetch(title=TITLE)
    assert again['already_present'] and again['parse_metadata']['method']=='mineru+grobid'

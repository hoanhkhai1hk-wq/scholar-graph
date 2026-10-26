"""Graph transport proof sidecars keep the frozen GraphEdge unchanged."""
import copy
from xml.etree.ElementTree import SubElement

import pytest
from fastapi.testclient import TestClient
from defusedxml import ElementTree as ET

from scholar_graph.api import create_app
from scholar_graph.errors import PipelineError
from scholar_graph.graph_service import build_graph, validate_graph
from scholar_graph.grobid import GrobidClient
from scholar_graph.normalize import reference_entries, citation_links
from scholar_graph.validation import ContractGate
from graph_samples import graph_bundles
from test_grobid_evidence import TEI
from test_validation_status import example_bundle


def test_graph_endpoint_proofs_cover_all_edges_without_changing_records(tmp_path):
    app = create_app(data_dir=tmp_path)
    bundles = graph_bundles()
    for b in bundles:
        app.state.repository.store.paper(b)
    value = TestClient(app).get('/api/v1/graph', params=[('paper_ids', b['paper_meta']['id']) for b in bundles]).json()
    diagnostics = value['diagnostics']
    assert diagnostics['reference_count'] == diagnostics['resolved_reference_count'] == 2
    assert diagnostics['unresolved_reference_count'] == 0
    for proof in diagnostics['edge_evidence']:
        edge = value['edges'][proof['edge_index']]
        assert set(edge) == {'schema_version', 'from_paper_id', 'to_paper_id', 'anchor', 'status'}
        assert proof['anchor'] == edge['anchor']
        b = next(b for b in bundles if b['paper_meta']['id'] == edge['from_paper_id'])
        assert proof['body_quote'] == b['chunks'][0]['text']
        assert proof['references'][0]['ref_id'] == b['reference_entries'][0]['ref_id']
        assert proof['references'][0]['method'] == 'doi' and proof['references'][0]['evidence']
        app.state.repository.gate.record('GraphEdge', edge)


@pytest.mark.parametrize('field', ['method', 'reference_number', 'bibliography'])
def test_fabricated_graph_identity_sidecar_is_rejected(field):
    bundles, gate = graph_bundles(), ContractGate()
    value = build_graph(bundles, gate)
    value['diagnostics']['edge_evidence'][0]['references'][0][field] = 'fabricated'
    with pytest.raises(PipelineError):
        validate_graph(value, bundles, gate)


def test_legacy_null_reference_fields_use_anchored_bibliography_without_mutation():
    bundles = graph_bundles()[:2]
    source, target = bundles
    ref = source['reference_entries'][0]
    ref.update(title=None, authors=[], year=None, doi=None, arxiv_id=None)
    bib = copy.deepcopy(source['chunks'][0])
    bib.update(chunk_id='bibliography', section_path=['References'], heading_1='References',
               heading_2=None, heading_3=None,
               text='[1] Demo Author. Synthetic Graph Study B. A venue, 2020.')
    source['chunks'].append(bib)
    target['reference_entries'], target['citation_links'] = [], []
    before = copy.deepcopy(bundles)
    value = build_graph(bundles, ContractGate())
    proof = value['diagnostics']['edge_evidence'][0]['references'][0]
    assert proof['method'] == 'title'
    assert proof['bibliography'][0]['anchor']['chunk_id'] == 'bibliography'
    assert proof['bibliography'][0]['quote'] == bib['text']
    assert value['edges'][0]['status'] == 'verified'
    assert bundles == before


def test_unnumbered_author_year_chain_has_real_body_and_bibliography_anchors():
    bundles = graph_bundles()[:2]
    source, target = bundles
    target['reference_entries'], target['citation_links'] = [], []
    source['chunks'][0]['text'] = 'Following Demo et al. (2020), we compare the calibration.'
    target['paper_meta'].update(title='Synthetic Graph Study B', authors=['Author Demo', 'Second Author'], year=2020)
    bib = {**source['chunks'][0], 'chunk_id': 'bib', 'section_path': ['References'], 'heading_1': 'References',
        'heading_2': None, 'heading_3': None,
        'text': 'Author Demo and Second Author. 2020. Synthetic Graph Study B. A Venue.'}
    source['chunks'].append(bib)
    source['reference_entries'] = reference_entries(source['chunks'], source['paper_meta']['id'])
    source['citation_links'] = citation_links(source['chunks'], source['reference_entries'])
    value = build_graph(bundles, ContractGate())
    assert len(value['edges']) == 1 and value['edges'][0]['status'] == 'verified'
    proof = value['diagnostics']['edge_evidence'][0]
    assert proof['anchor']['chunk_id'] == source['chunks'][0]['chunk_id']
    assert proof['references'][0]['bibliography'][0]['anchor']['chunk_id'] == 'bib'


def test_unresolved_is_counted_and_never_creates_edge():
    bundles = graph_bundles()[:2]
    bundles[0]['reference_entries'][0].update(title=None, authors=[], year=None, doi=None, arxiv_id=None)
    bundles[1]['reference_entries'], bundles[1]['citation_links'] = [], []
    graph = build_graph(bundles, ContractGate())
    assert graph['edges'] == []
    assert graph['diagnostics']['reference_count'] == graph['diagnostics']['unresolved_reference_count'] == 1
    assert graph['diagnostics']['reference_resolutions'][0]['status'] == 'unresolved'
    assert graph['diagnostics']['reference_resolutions'][0]['method'] is None


def test_grobid_reference_arxiv_idno_extracted_without_contract_fields():
    tree = ET.fromstring(TEI)
    namespace = '{http://www.tei-c.org/ns/1.0}'
    item = tree.find('.//' + namespace + 'listBibl/' + namespace + 'biblStruct')
    SubElement(item, namespace + 'idno', {'type': 'arXiv'}).text = '1706.03762v7'
    bundle = GrobidClient('http://127.0.0.1:8070')._convert(example_bundle(), tree)
    assert bundle['reference_entries'][0]['arxiv_id'] == '1706.03762v7'
    ContractGate().bundle(bundle)

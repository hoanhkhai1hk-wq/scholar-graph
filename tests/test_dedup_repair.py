"""Regression fixtures are self-made; official pdf/ 真文件 are measured separately."""
import copy
from urllib.parse import unquote

from fastapi.testclient import TestClient
from reportlab.pdfgen import canvas

from scholar_graph.api import create_app
from scholar_graph.storage import RecordStore
from scholar_graph.validation import ContractGate
from test_dedup import versions


def test_upload_downgrade_warns_and_publishes_existing_contracts(tmp_path):
    client = TestClient(create_app(data_dir=tmp_path / 'records'))
    responses = []
    for version in ('v7', 'v1'):
        path = tmp_path / (version + '.pdf')
        doc = canvas.Canvas(str(path), invariant=1)
        doc.setTitle('')
        doc.setAuthor('')
        doc.drawString(40, 730, 'arXiv:1706.03762' + version)
        doc.drawString(40, 700, 'A shared experimental paper with evidence for twelve samples.')
        doc.drawString(40, 670, 'Revised protocol.' if version == 'v7' else 'Original protocol.')
        doc.save()
        responses.append(client.post('/api/v1/papers', files={'file': (path.name, path.read_bytes(), 'application/pdf')}))
    assert [r.status_code for r in responses] == [201, 201]
    assert '建议保留库里较新版本（v7）' in unquote(responses[1].headers['X-ScholarGraph-Dedup-Warning'])
    ContractGate().record('PaperMeta', responses[1].json())  # No extra warning field in frozen record.
    pid = responses[1].json()['id']
    decision = client.get(f'/api/v1/papers/{pid}/dedup-decision')
    assert decision.status_code == 200 and decision.json()['recommendation'] == 'keep_old'
    assert decision.json()['new_paper_id'] == pid
    assert client.get(f'/api/v1/papers/{pid}/diff-summary').status_code == 200


def test_missing_identity_uses_dice_but_conflicting_doi_never_pairs(tmp_path):
    old, new = versions()
    for bundle in (old, new):
        bundle['paper_meta'].update(title=None, authors=[], doi=None, arxiv_id=None)
    new['chunks'][0]['text'] = old['chunks'][0]['text'] + ' Revised.'
    store = RecordStore(tmp_path, ContractGate())
    store.paper(old)
    assert store.previous_version(new['paper_meta']) is None
    assert store.dedup_candidate(new)['paper_meta']['id'] == old['paper_meta']['id']
    left, right = copy.deepcopy(old), copy.deepcopy(new)
    left['paper_meta']['doi'], right['paper_meta']['doi'] = '10.5555/left', '10.5555/right'
    other = RecordStore(tmp_path / 'conflict', ContractGate())
    other.paper(left)
    assert other.dedup_candidate(right) is None


def test_unrelated_text_has_no_false_warning(tmp_path):
    old, new = versions()
    for bundle in (old, new):
        bundle['paper_meta'].update(title=None, authors=[], doi=None, arxiv_id=None)
    new['chunks'][0]['text'] = 'Entirely unrelated astronomy observation distant galaxy.'
    store = RecordStore(tmp_path, ContractGate())
    store.paper(old)
    assert store.dedup_candidate(new) is None

"""Formula correction provenance/validation, not recognition quality evidence."""
import hashlib
import json
from pathlib import Path

from fastapi.testclient import TestClient
import pytest
from scholar_graph.api import create_app
from scholar_graph.errors import PipelineError
from scholar_graph.workspace_formulas import formula_model
from test_validation_status import example_bundle


@pytest.fixture
def context(tmp_path):
    app=create_app(data_dir=tmp_path); bundle=example_bundle()
    app.state.repository.store.paper(bundle); pid=bundle['paper_meta']['id']; w=app.state.workspace
    region={'paper_id':pid,'source_file_hash':bundle['paper_meta']['file_hash'],
            'region_id':'p0001-r0000','bbox':[.1,.2,.5,.3],'page_number':1,'latex':'x_{wrong}',
            'status':'recognized_unreviewed','notice':'unreviewed','model':'PP-FormulaNet-S'}
    w.put('formula',pid+':'+region['region_id'],region)
    return TestClient(app),app,bundle,region


def frozen(app):
    return {str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in (app.state.repository.root/'papers').rglob('*.json')}


def test_formula_correction_retains_machine_candidate_source_history_and_restart(context):
    client,app,bundle,row=context; pid=bundle['paper_meta']['id']; before=frozen(app)
    path=f'/api/v2/papers/{pid}/formulas'
    assert client.patch(path+'/'+row['region_id'],json={'latex':r'x_{correct}','note':'Checked original subscript'}).status_code==200
    value=client.get(path).json()['items'][0]
    assert value['latex']==r'x_{correct}' and value['recognized_latex']=='x_{wrong}'
    assert value['status']=='corrected_from_source' and value['correction']['source_file_hash']==bundle['paper_meta']['file_hash']
    fresh=TestClient(create_app(data_dir=app.state.repository.root))
    assert fresh.get(path).json()['items'][0]['latex']==r'x_{correct}'
    assert app.state.workspace.read('formula',pid+':'+row['region_id'])['latex']=='x_{wrong}'
    with app.state.workspace.connect() as db:
        assert db.execute("SELECT COUNT(*) FROM audit WHERE action='formula_corrected'").fetchone()[0]==1
    assert frozen(app)==before


@pytest.mark.parametrize('body',[{'latex':'x}','note':'bad braces'}, {'latex':'x','note':'  '},
                               {'latex':r'\input{private}','note':'bad command'}, {'latex':'x','note':'ok','paper_id':'other'}])
def test_invalid_formula_correction_never_publishes(context,body):
    client,app,bundle,row=context
    r=client.patch(f'/api/v2/papers/{bundle["paper_meta"]["id"]}/formulas/{row["region_id"]}',json=body)
    assert r.status_code==422
    assert app.state.workspace.all('formula_correction')==[]


def test_unprepared_formula_model_is_an_explicit_error_not_invented_latex(tmp_path,monkeypatch):
    monkeypatch.setenv('SCHOLAR_GRAPH_FORMULA_MODEL_DIR',str(tmp_path/'absent'))
    with pytest.raises(PipelineError,match='未生成或编造'):
        formula_model()

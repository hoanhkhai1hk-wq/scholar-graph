import json
from types import SimpleNamespace

import pytest

from scholar_graph.adapters import LocalEngines


@pytest.mark.parametrize('shared',[True,False])
def test_public_ocr_cache_configuration_preserves_worker_and_removes_credentials(tmp_path,monkeypatch,shared):
    calls=[]
    monkeypatch.setenv('DEEPSEEK_API_KEY','explicit-synthetic-test-value')
    monkeypatch.delenv('SCHOLAR_GRAPH_OCR_CACHE_DIR',raising=False)
    if shared:
        monkeypatch.setenv('SCHOLAR_GRAPH_OCR_CACHE_DIR',str(tmp_path/'shared-weights'))
    monkeypatch.setattr('scholar_graph.adapters.subprocess.run',lambda argv,**kw:
        calls.append((argv,kw)) or SimpleNamespace(returncode=0,stdout=json.dumps({'pages':[]}).encode()))
    engine=LocalEngines(cache_dir=tmp_path/'local')
    assert engine.ocr(tmp_path/'selfmade.pdf',[0])=={'pages':[]}
    argv,kwargs=calls[0]
    expected=tmp_path/'shared-weights' if shared else tmp_path/'local/paddlex'
    assert kwargs['env']['PADDLE_PDX_CACHE_HOME']==str(expected.resolve())
    assert 'DEEPSEEK_API_KEY' not in kwargs['env']
    assert argv[-1]=='[0]' and kwargs['timeout']==300

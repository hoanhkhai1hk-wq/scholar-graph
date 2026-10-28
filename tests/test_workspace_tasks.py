"""Durability, cancellation and source validation; simulated model output is explicit."""
import copy
import threading
import time

import pytest
from scholar_graph.api import create_app
from scholar_graph.errors import PipelineError
from scholar_graph.workspace_tasks import TaskRunner
from scholar_graph.workspace_translation import translation_task
from scholar_graph.workspace_writing import validated_document
from scholar_graph.workspace_writing import numeric_values, repair_paragraphs
from scholar_graph.grounded_model import evidence_candidates
from test_validation_status import example_bundle


def test_writing_group_labels_do_not_hide_experimental_counts():
    assert numeric_values('这两条路径从两个角度描述方法。') == set()
    assert numeric_values('四条相互交织的研究主线') == set()
    assert numeric_values('零样本迁移、zero-shot 与 ZeRO 方法') == set()
    assert numeric_values('zero errors and 0% loss') == {'0','0%'}
    assert numeric_values('两种不同的使用范式；两种使用方式') == set()
    assert numeric_values('First, precompute once. Second, reuse it.') == {'1','2'}
    assert numeric_values('使用两块GPU与8个样本。') == {'2', '8'}
    assert numeric_values('使用2个GPU，准确率90%。') == {'2', '90%'}


def test_paragraph_repair_preserves_accepted_paragraphs():
    class SimulatedClient:
        def complete(self, *args, **kwargs):
            return {'content':'{"repairs":[{"index":1,"paragraph":{"text":"修正段落","type":"proposal","citations":[]}}]}'}
    original = {'title':'测试草稿','sections':[{'paragraphs':[{'text':'保留段落'},{'text':'错误段落'}]}]}
    error = PipelineError('VALIDATION_ERROR','模拟校验失败',details={'paragraph_indices':[1]})
    fixed = repair_paragraphs(SimulatedClient(),original,error,[])
    assert fixed['sections'][0]['paragraphs'][0] == original['sections'][0]['paragraphs'][0]
    assert fixed['sections'][0]['paragraphs'][1]['text'] == '修正段落'
    assert original['sections'][0]['paragraphs'][1]['text'] == '错误段落'


def test_proposal_process_is_allowed_but_uncited_prior_findings_are_not(context):
    workspace, _, bundle = context
    def document(text):
        return {'title':'研究方案','sections':[{'kind':k,'title':k,'paragraphs':[{'text':text,'type':'proposal','citations':[]}]} for k in ('abstract','introduction','related_work')]}
    value = document('我们计划区分已确立的发现与待验证设想，并逐项复核。')
    assert validated_document(value,[],[bundle],workspace.repository.gate,'outline')
    with pytest.raises(PipelineError,match='既有结果'):
        validated_document(document('已有工作分别确立了模型的有效性。'),[],[bundle],workspace.repository.gate,'outline')


def wait_finished(runner, task):
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        value = runner.get(task['id'])
        if value['status'] not in ('queued', 'running', 'cancelling'):
            return value
        time.sleep(.01)
    raise AssertionError('Task did not finish')


@pytest.fixture
def context(tmp_path):
    app = create_app(data_dir=tmp_path / 'records')
    bundle = example_bundle()
    app.state.repository.store.paper(bundle)
    yield app.state.workspace, app.state.workspace_tasks, bundle
    app.state.workspace_tasks.stop()


def test_active_cancel_is_honest_and_restart_keeps_result(context):
    workspace, runner, _ = context
    entered, release = threading.Event(), threading.Event()
    def work(identity, parameters, service):
        entered.set(); release.wait(3)
        return {'succeeded_count': 1, 'failed_count': 0, 'value': 7}
    runner.handlers['probe'] = work
    task = runner.submit('probe', {'internal_path': 'never-public'})
    assert entered.wait(2)
    assert runner.cancel(task['id'])['status'] == 'cancelling'
    assert 'parameters' not in runner.get(task['id'])
    release.set()
    final = wait_finished(runner, task)
    assert final['status'] == 'cancelled'
    assert final['result']['value'] == 7  # Completed atomic work is not silently erased.
    assert TaskRunner(workspace).get(task['id']) == final


def test_restart_marks_unfinished_task_interrupted(context):
    workspace, runner, _ = context
    workspace.put('task', 'old', {'id': 'old', 'kind': 'probe', 'status': 'running', 'parameters': {}, 'cancel_requested': False})
    runner.start()
    assert runner.get('old')['status'] == 'interrupted'


def test_translation_retry_reuses_checked_batches_and_covers_last_page(context, monkeypatch):
    workspace, runner, bundle = context
    original = bundle['chunks'][0]
    bundle['paper_meta']['id'] = 'longbook-translation-test'
    bundle['paper_meta']['page_count'] = 541
    bundle['chunks'] = [{**original, 'paper_id': bundle['paper_meta']['id'], 'chunk_id': f'c{i}', 'page_number': 1 if i == 0 else 541, 'text': 'Source words. ' * 700} for i in range(2)]
    bundle['reference_entries'], bundle['citation_links'] = [], []
    workspace.repository.store.paper(bundle)
    calls = []
    def translate(self, paper_id, **kwargs):
        chunks = self.repository.paper(paper_id)['chunks']; calls.append(chunks[0]['chunk_id'])
        return {'paper_id': paper_id, 'target': 'zh', 'scope': 'full', 'markdown': None,
            'segments': [{'source_chunk_id': c['chunk_id'], 'paper_id': paper_id, 'page_number': c['page_number'], 'section_path': c['section_path'], 'type': c['type'], 'source_text': c['text'], 'translated_text': '模拟译文'} for c in chunks],
            'metadata': {'model': 'simulated-test', 'model_calls': []}}
    monkeypatch.setattr('scholar_graph.workspace_translation.Translator.translate', translate)
    runner.handlers['translation'] = lambda identity, parameters, service: translation_task(workspace, identity, parameters, service)
    parameters = {'paper_id': bundle['paper_meta']['id'], 'scope': 'full', 'target': 'zh'}
    result = wait_finished(runner, runner.submit('translation', parameters))
    assert result['result']['translation']['metadata']['complete']
    assert result['result']['translation']['segments'][-1]['page_number'] == 541
    repeated = wait_finished(runner, runner.submit('translation', parameters))
    assert len(calls) == 2 and repeated['result']['translation']['metadata']['cache_hits'] == 2


def test_writing_rejects_invented_numbers_and_citations(context):
    workspace, _, bundle = context
    candidates = evidence_candidates(bundle, 'abstract method', limit=4)
    if not candidates:
        c = bundle['chunks'][0]
        from scholar_graph.validation import chunk_anchor
        candidates = [{'evidence_id': 'e1', 'paper_id': c['paper_id'], 'anchor': chunk_anchor(c), 'quote': c['text']}]
    source = candidates[0]
    paragraph = {'text': '本文讨论所选文献的方法。', 'type': 'synthesis', 'citations': [{'evidence_id': source['evidence_id'], 'quote': source['quote'][:100]}]}
    value = {'title': '测试框架', 'sections': [{'kind': k, 'title': k, 'paragraphs': [copy.deepcopy(paragraph)]} for k in ('abstract', 'introduction', 'related_work')]}
    good = validated_document(copy.deepcopy(value), candidates, [bundle], workspace.repository.gate, 'outline')
    assert good['references'][0]['paper_id'] == bundle['paper_meta']['id']
    value['sections'][0]['paragraphs'][0]['text'] = '实验达到987654321。'
    with pytest.raises(PipelineError, match='数字'):
        validated_document(copy.deepcopy(value), candidates, [bundle], workspace.repository.gate, 'outline')
    value['sections'][0]['paragraphs'][0] = copy.deepcopy(paragraph)
    value['sections'][0]['paragraphs'][0]['citations'][0]['evidence_id'] = 'invented'
    with pytest.raises(PipelineError, match='不存在'):
        validated_document(value, candidates, [bundle], workspace.repository.gate, 'outline')


def test_writing_ids_attach_exact_substantive_source_and_reject_header_only(context):
    from scholar_graph.workspace_writing import writing_evidence
    workspace, _, bundle = context
    source = bundle['chunks'][0]
    source['text']='This paper describes an attention architecture with a source-grounded encoder and decoder. '*3
    source['section_path']=['Method']
    source['heading_1']='Method';source['heading_2']=source['heading_3']=None
    candidates=writing_evidence(bundle,'architecture method',4)
    assert candidates and all(len(c['quote'])>=80 for c in candidates)
    paragraph={'text':'本文讨论注意力方法。','type':'synthesis','citations':[{'evidence_id':candidates[0]['evidence_id']}]}
    value={'title':'来源核对','sections':[{'kind':kind,'title':kind,'paragraphs':[copy.deepcopy(paragraph)]} for kind in ['abstract','introduction','related_work']]}
    result=validated_document(value,candidates,[bundle],workspace.repository.gate,'outline')
    assert result['sections'][0]['paragraphs'][0]['citations'][0]['quote']==candidates[0]['quote']
    candidates[0]['quote']=source['text']='Method'
    with pytest.raises(PipelineError,match='实质性'):
        validated_document({'title':'来源核对','sections':[{'kind':kind,'title':kind,'paragraphs':[copy.deepcopy(paragraph)]} for kind in ['abstract','introduction','related_work']]},candidates,[bundle],workspace.repository.gate,'outline')

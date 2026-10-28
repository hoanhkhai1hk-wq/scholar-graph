import copy
import asyncio
import json
import pytest
from scholar_graph.workspace_research import validate_research, values, operand_number, research_stream
from scholar_graph.validation import ContractGate, chunk_anchor
from scholar_graph.errors import PipelineError
from test_validation_status import example_bundle
from scholar_graph.workspace_overview import is_overview_question, overview_evidence
from scholar_graph.grounded_model import evidence_candidates


def material():
    bundle = example_bundle(); chunk = bundle['chunks'][0]
    chunk['text'] = 'The current score is 28.4 BLEU. The previous score is 26.36 BLEU. We use 8 P100 GPUs. The model has 1.5B parameters.'
    bundle['reference_entries'], bundle['citation_links'] = [], []
    return bundle, [{'evidence_id': 'e1', 'paper_id': chunk['paper_id'], 'anchor': chunk_anchor(chunk), 'quote': chunk['text']}]


@pytest.mark.parametrize('question', ['这篇论文关于什么的', '这篇论文讲什么？', '这篇论文的主要内容是什么', '请总结一下这篇论文', 'What is this paper about?'])
def test_overview_intent_is_limited_to_broad_summary_questions(question):
    assert is_overview_question(question)


@pytest.mark.parametrize('question', ['这篇论文用多少个GPU？', '这篇论文为什么没有提到Transformer？', '这篇论文作者是谁？', '这篇论文讨论了什么数据集？'])
def test_specific_or_false_premise_questions_are_not_overview(question):
    assert not is_overview_question(question)


def test_overview_uses_only_source_abstract_or_introduction_not_metadata():
    bundle = example_bundle()
    chunk = bundle['chunks'][0]
    chunk['text'] = 'We propose a model based on attention mechanisms for sequence transduction.'
    chunk['section_path'] = []
    bundle['paper_meta']['abstract'] = 'Unverified user-provided summary must never become a source quotation.'
    bundle['reference_entries'], bundle['citation_links'] = [], []
    class State:
        def __init__(self, proof): self.proof = proof
        def read(self, kind, identity, default): return {'front_matter_proofs': {'abstract': self.proof}}
    question = '这篇论文关于什么的'
    assert evidence_candidates(bundle, question) == []
    assert overview_evidence(State([]), bundle, question) == []
    evidence = overview_evidence(State([chunk['chunk_id']]), bundle, question)
    assert evidence and evidence[0]['quote'] == chunk['text']
    assert evidence[0]['anchor'] == chunk_anchor(chunk)
    assert 'Unverified user-provided summary' not in str(evidence)
    assert overview_evidence(State([chunk['chunk_id']]), bundle, '这篇论文用了多少GPU？') == []


def test_overview_falls_back_to_real_introduction_when_abstract_missing():
    bundle = example_bundle(); chunk = bundle['chunks'][0]
    chunk['text'] = 'This paper introduces a concrete method for scientific document processing.'
    chunk['section_path'] = ['1 Introduction']
    class State:
        def read(self, kind, identity, default): return {}
    evidence = overview_evidence(State(), bundle, '这篇论文讲什么？')
    assert evidence[0]['anchor'] == chunk_anchor(chunk)
    assert evidence[0]['quote'] == chunk['text']


def test_decimal_improvement_has_two_real_source_operands():
    bundle, evidence = material()
    cited = {'evidence_id': 'e1', 'quote': evidence[0]['quote']}
    value = {'refused': False, 'paragraphs': [{'text': '当前模型为28.4 BLEU，基线为26.36 BLEU。', 'kind': 'answer', 'citations': [cited]}],
             'calculations': [{'label': 'BLEU提升', 'operation': 'subtract', 'unit': 'BLEU', 'operands': [
                 {'label': '当前', 'value': '28.4', **cited}, {'label': '基线', 'value': '26.36', **cited}]}]}
    checked = validate_research(value, evidence, [bundle], ContractGate(), '提升多少？')
    assert checked['calculations'][0]['result'] == '2.04'
    assert checked['calculations'][0]['operands'][0]['anchor'] == evidence[0]['anchor']
    bad = copy.deepcopy(value); bad['paragraphs'][0]['text'] = '达到98.6 BLEU。'
    with pytest.raises(PipelineError, match='数值'):
        validate_research(bad, evidence, [bundle], ContractGate(), '得分？')


def test_units_and_chinese_gpu_counts_do_not_change_numeric_meaning():
    assert values('1.5B parameters') == values('15亿参数')
    assert values('八块P100 GPU') == values('8 P100 GPUs')
    bundle, evidence = material()
    value = {'refused': False, 'paragraphs': [{'text': '模型包含1.5M参数。', 'kind': 'answer', 'citations': [{'evidence_id': 'e1', 'quote': evidence[0]['quote']}]}], 'calculations': []}
    with pytest.raises(PipelineError, match='单位'):
        validate_research(value, evidence, [bundle], ContractGate(), '参数？')


def test_missing_evidence_is_explicit_refusal_and_unknown_citations_fail():
    bundle, evidence = material()
    value = {'refused': True, 'paragraphs': [{'text': '当前原文没有提供这项信息。', 'kind': 'limitation', 'citations': []}], 'calculations': []}
    assert validate_research(value, evidence, [bundle], ContractGate(), '未知信息？')['refused']
    value['paragraphs'][0]['citations'] = [{'evidence_id': 'invented', 'quote': 'fake'}]
    with pytest.raises(PipelineError, match='不存在'):
        validate_research(value, evidence, [bundle], ContractGate(), '未知信息？')


def test_overview_evidence_id_attaches_only_checked_original_source():
    bundle, evidence = material()
    value = {'refused': False, 'paragraphs': [{'text': '论文报告了实验结果。', 'kind': 'answer',
                                               'citations': [{'evidence_id': 'e1'}]}], 'calculations': []}
    with pytest.raises(PipelineError, match='格式'):
        validate_research(value, evidence, [bundle], ContractGate(), '这篇论文讲什么？')
    result = validate_research(value, evidence, [bundle], ContractGate(), '这篇论文讲什么？', allow_source_ids=True)
    assert result['paragraphs'][0]['citations'][0]['quote'] == evidence[0]['quote']
    assert result['paragraphs'][0]['citations'][0]['anchor'] == evidence[0]['anchor']
    value['paragraphs'][0]['citations'][0]['evidence_id'] = 'nonexistent'
    with pytest.raises(PipelineError, match='不存在'):
        validate_research(value, evidence, [bundle], ContractGate(), '这篇论文讲什么？', allow_source_ids=True)


def test_empty_retrieval_never_claims_the_entire_paper_lacks_information():
    bundle, _ = material()
    result = validate_research({'refused': True, 'paragraphs': [{'text': '论文没有此内容。',
        'kind': 'limitation', 'citations': []}]}, [], [bundle], ContractGate(), '论文中是否提到火星？')
    assert result['refused'] and '未检索到' in result['paragraphs'][0]['text']
    assert '不能证明' in result['paragraphs'][0]['text']


def test_irrelevant_retrieved_passages_do_not_prove_full_paper_absence():
    bundle, evidence = material()
    value = {'refused': True, 'paragraphs': [{'text': '所给证据中没有火星数据；该论文的实验仅涉及机器翻译，未提及火星探测任务。',
             'kind': 'limitation', 'citations': [{'evidence_id': 'e1', 'quote': evidence[0]['quote']}]}]}
    result = validate_research(value, evidence, [bundle], ContractGate(), '火星任务准确率？')
    assert result['refused'] and '不能证明' in result['paragraphs'][0]['text']
    assert not result['paragraphs'][0]['citations']


def test_zero_evidence_stream_refuses_without_model_calls_or_fake_tokens(monkeypatch):
    bundle, _ = material()
    class Repository:
        gate = ContractGate()
        def paper(self, identity): return bundle
    class Workspace:
        def read(self, kind, identity, default): return {}
    from scholar_graph.deepseek_client import DeepSeekClient
    def should_not_call(*args, **kwargs):
        raise AssertionError('No model call is needed for an empty evidence list')
    monkeypatch.setattr(DeepSeekClient, 'environment', should_not_call)
    monkeypatch.setenv('SCHOLAR_GRAPH_WORKSPACE_RETRIEVAL', 'lexical')
    async def collect():
        response = research_stream(Workspace(), Repository(), [bundle['paper_meta']['id']], '论文里火星基地的建造预算是多少？')
        return [frame async for frame in response.body_iterator]
    frames = asyncio.run(collect())
    assert not any('\nevent: draft\n' in frame for frame in frames)
    modes = [json.loads(frame.split('\ndata: ',1)[1].strip()) for frame in frames if '\nevent: mode\n' in frame]
    final = next(json.loads(frame.split('\ndata: ',1)[1].strip()) for frame in frames if '\nevent: final\n' in frame)
    assert modes[-1]['mode'] == 'evidence_refusal' and modes[-1]['token_streaming'] is False
    assert final['refused'] and final['metadata']['model_calls'] == []
    assert '不能证明' in final['paragraphs'][0]['text']


def test_model_names_and_scales_before_chinese_are_not_spurious_quantities():
    assert values('GPT-1论文没有报告参数，GPT-3为175 billion参数。') == values('1750亿参数')
    assert values('β₁=0.9、β₂=0.98') == values('0.9 0.98')
    assert values('额外增加一层') <= values('an additional layer normalization')
    assert operand_number('117M') == 117000000
    assert operand_number('175 billion') == 175000000000
    with pytest.raises(PipelineError):
        operand_number('1.5M + 3B')


def test_corrective_refusal_can_repeat_false_premise_but_not_affirm_it():
    bundle, evidence = material()
    evidence[0]['quote'] = bundle['chunks'][0]['text'] = 'We use Adam with β1 = 0.9 and β2 = 0.98.'
    paragraph = {'text': '题设β₁=0.5、β₂=0.6不符，原文是0.9和0.98。', 'kind': 'limitation',
                 'citations': [{'evidence_id': 'e1', 'quote': evidence[0]['quote']}]}
    value = {'refused': True, 'paragraphs': [paragraph]}  # Empty calculations may be omitted.
    assert validate_research(value, evidence, [bundle], ContractGate(), 'β₁=0.5、β₂=0.6对吗？')['refused']
    value['refused'] = False; paragraph['kind'] = 'answer'; paragraph['text'] = '是的，β₁=0.5。'
    with pytest.raises(PipelineError):
        validate_research(value, evidence, [bundle], ContractGate(), 'β₁=0.5、β₂=0.6对吗？')


def test_section_labels_are_source_checked_and_do_not_mask_wrong_values():
    bundle, evidence = material()
    bundle['chunks'][0]['section_path'] = ['5.2 Hardware and Schedule']
    evidence[0]['anchor'] = chunk_anchor(bundle['chunks'][0])
    paragraph = {'text': '第5.2节使用8块P100 GPU。', 'kind': 'answer',
                 'citations': [{'evidence_id': 'e1', 'quote': evidence[0]['quote']}]}
    value = {'refused': False, 'paragraphs': [paragraph]}
    assert not validate_research(value, evidence, [bundle], ContractGate(), '多少GPU？')['refused']
    paragraph['text'] = '第5.3节使用9块P100 GPU。'
    with pytest.raises(PipelineError):
        validate_research(value, evidence, [bundle], ContractGate(), '多少GPU？')


def test_compound_translation_terms_do_not_require_conflicting_substrings():
    from scholar_graph.translation import check_terms, used_terms
    glossary = {'成分句法分析': 'constituency parsing', '移进-归约成分句法分析': 'shift-reduce constituent parsing'}
    assert list(used_terms('移进-归约成分句法分析', glossary)) == ['移进-归约成分句法分析']
    check_terms('移进-归约成分句法分析', 'shift-reduce constituent parsing', glossary)
    with pytest.raises(PipelineError):
        check_terms('移进-归约成分句法分析', 'unrelated task', glossary)

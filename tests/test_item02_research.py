"""Deterministic numeric binding failures, separate from real-model acceptance."""
import pytest
from scholar_graph.workspace_research import validate_research
from scholar_graph.validation import ContractGate,chunk_anchor
from scholar_graph.errors import PipelineError
from test_validation_status import example_bundle
from scholar_graph.vector_worker import reranker_thread_count
from item02.audit_rules import context_transition_supported, unsupported_metric_refused,result_digest,source_review_matches


def test_audit_accepts_attributed_transition_without_unnecessary_older_page():
    citation={'anchor':{'paper_id':'gpt2','page_number':4},'quote':'We also increase the context size from 512 to 1024 tokens.'}
    assert context_transition_supported([citation],'gpt2')
    assert not context_transition_supported([dict(citation,quote='A batchsize of 512 and context of 1024 tokens.')],'gpt2')
    assert not context_transition_supported([dict(citation,anchor={'paper_id':'gpt1','page_number':4})],'gpt2')


def test_audit_distinguishes_repeating_false_premise_from_asserting_metric():
    refusal={'refused':True,'paragraphs':[{'kind':'limitation','text':'并未报告准确率为97.3%，没有给出BERT对应数据，因此无法计算。'}],'calculations':[]}
    assert unsupported_metric_refused(refusal)
    assert unsupported_metric_refused(dict(refusal,paragraphs=[{'kind':'limitation','text':'当前检索到的原文证据不足以回答；这不能证明论文中没有相关内容。'}]))
    assert not unsupported_metric_refused(dict(refusal,refused=False))
    assert not unsupported_metric_refused(dict(refusal,paragraphs=[{'kind':'answer','text':'Base准确率97.3%，高出1个百分点。'}]))
    assert not unsupported_metric_refused(dict(refusal,calculations=[{'result':'1'}]))


def test_refusal_structure_does_not_claim_to_prove_language_meaning():
    limitation={'refused':True,'paragraphs':[{'kind':'limitation','text':'证据中没有任何相关内容，无法给出差值。'}],'calculations':[]}
    assert unsupported_metric_refused(limitation)
    assert not source_review_matches(limitation,None)
    # Even a misleadingly tagged refusal requires a semantic source review.
    false_claim=dict(limitation,paragraphs=[{'kind':'limitation','text':'准确率是97.3%，高出1个百分点。'}])
    assert not source_review_matches(false_claim,{'passed':False,'notes':'Fabricated metric','result_sha256':result_digest(false_claim)})


def test_missing_failed_or_stale_source_review_cannot_approve_answer():
    value={'paragraphs':[{'text':'Answer A'}]}
    review={'passed':True,'notes':'Checked against physical source page','result_sha256':result_digest(value)}
    assert source_review_matches(value,review)
    assert not source_review_matches(value,dict(review,passed=False))
    assert not source_review_matches(value,dict(review,notes=''))
    assert not source_review_matches({'paragraphs':[{'text':'Answer B'}]},review)


def test_reranker_thread_configuration_is_bounded_and_does_not_exceed_available_cpus():
    assert reranker_thread_count({},16)==8
    assert reranker_thread_count({},4)==4
    assert reranker_thread_count({'SCHOLAR_GRAPH_RERANKER_THREADS':'2'},16)==2
    for value in ['0','17','unbounded']:
        with pytest.raises(ValueError): reranker_thread_count({'SCHOLAR_GRAPH_RERANKER_THREADS':value},16)


@pytest.mark.parametrize('answer,valid',[
    ('β₁=0.9，β₂=0.98。',True),('β₁=0.98，β₂=0.9。',False),
    ('beta_1=0.9; beta_2=0.98',True),('β_{1}=0.98',False)])
def test_named_beta_values_cannot_be_swapped_even_when_both_digits_are_in_quote(answer,valid):
    bundle=example_bundle(); chunk=bundle['chunks'][0]
    chunk['text']='We used Adam with β1 = 0.9 and β2 = 0.98.'
    evidence=[{'evidence_id':'e1','anchor':chunk_anchor(chunk),'quote':chunk['text']}]
    document={'refused':False,'paragraphs':[{'text':answer,'kind':'answer','citations':[{'evidence_id':'e1','quote':chunk['text']}]}],'calculations':[]}
    if valid:
        assert not validate_research(document,evidence,[bundle],ContractGate(),'Adam参数是什么？')['refused']
    else:
        with pytest.raises(PipelineError,match='不能交换'):
            validate_research(document,evidence,[bundle],ContractGate(),'Adam参数是什么？')

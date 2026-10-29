"""Protocol/intent controls; real answer-quality and browser evidence are separate."""
import copy
import pytest
from scholar_graph.errors import PipelineError
from scholar_graph.workspace_overview import is_overview_question,overview_evidence
from scholar_graph.workspace_query import is_relation_question,checked_queries,needs_bilingual_query,bilingual_queries
from scholar_graph.workspace_research import validate_research
from scholar_graph.validation import ContractGate,chunk_anchor
from test_validation_status import example_bundle

@pytest.mark.parametrize('question',['这篇论文的创新点是什么？','主要讲了啥？','它的主要贡献有哪些？','这篇文章的核心思想是什么？'])
def test_casual_overview_questions_are_recognized(question):
    assert is_overview_question(question)

@pytest.mark.parametrize('question',['这篇论文准确率是多少？','为什么这篇论文没有评估火星？','它是如何防御提示注入的？'])
def test_specific_or_false_premise_does_not_become_generic_overview(question):
    assert not is_overview_question(question)

def test_relation_requires_multiple_actual_selected_papers():
    for q in ['他们有什么关联','它们有什么关系？','这两篇有什么共同点和区别？']:
        assert is_relation_question(q,2)
        assert not is_relation_question(q,1)

def test_overview_boundary_uses_short_literal_heading_not_stale_section_path():
    bundle=example_bundle();original=bundle['chunks'][0]
    abstract={**original,'section_path':['Abstract'],'text':'We introduce a method based on anchored sources and verified quotations.'}
    heading={**original,'chunk_id':'intro-heading','section_path':['Abstract'],'text':'1. Introduction'}
    intro={**original,'chunk_id':'intro-body','section_path':['Abstract'],'text':'The related introduction must not silently become part of the abstract.'}
    bundle['chunks']=[abstract,heading,intro]
    workspace=type('W',(),{'read':lambda *args:{}})()
    rows=overview_evidence(workspace,bundle,'这篇论文讲什么？')
    assert [r['anchor']['chunk_id'] for r in rows]==[abstract['chunk_id']]
    assert overview_evidence(workspace,bundle,'他们有什么关联',for_comparison=True)==rows
    assert overview_evidence(workspace,bundle,'火星预算多少？')==[]

def test_rewrite_is_query_only_and_rejects_new_numbers():
    assert checked_queries({'queries':['prompt injection defense attention gates']},'它如何防止提示注入？')
    for value in [{'answer':'invented answer'},{'queries':['accuracy 99.9']},{'queries':['<instruction>']},
                  {'queries':['a','b','c']},{'queries':['valid\nextra instructions']}]:
        with pytest.raises(PipelineError):checked_queries(value,'怎么做？')

def test_rewrite_runs_only_for_empty_cross_language_retrieval():
    bundle=example_bundle();bundle['chunks'][0]['text']='An English source text discussing a neural architecture.'
    assert needs_bilingual_query('如何工作？',[bundle],[])
    assert not needs_bilingual_query('如何工作？',[bundle],[{'quote':'real source'}])
    assert not needs_bilingual_query('How does this work?',[bundle],[])
    bundle['chunks'][0]['text']='本研究讨论中文材料中的真实方法和原文定位。'
    assert not needs_bilingual_query('如何工作？',[bundle],[])

def test_query_timeout_is_bounded_and_restored_and_no_draft_is_published():
    class Client:
        timeout=60
        def stream_complete(self,messages,**kwargs):
            assert self.timeout==15 and kwargs['phase']=='workspace_query_rewrite'
            kwargs['on_delta']('private query fragment')
            return {'content':'{"queries":["method attention"]}'}
    c=Client();parts=[]
    assert bilingual_queries(c,'如何实现？',['Synthetic paper'],parts.append)==['method attention']
    assert c.timeout==60 and parts==['private query fragment']

def test_scope_count_is_checked_from_inputs_but_unrelated_numerical_facts_still_fail():
    first=example_bundle();first['chunks'][0]['text']='This paper studies neural architectures.'
    second=copy.deepcopy(first);second['paper_meta']['id']='second';second['chunks'][0].update(paper_id='second',chunk_id='second-chunk')
    second['reference_entries']=[];second['citation_links']=[]
    quote=first['chunks'][0]['text'];e=[{'evidence_id':'e1','quote':quote,'anchor':chunk_anchor(first['chunks'][0])}]
    value={'refused':False,'paragraphs':[{'kind':'answer','text':'这两篇论文讨论神经网络。','citations':[{'evidence_id':'e1','quote':quote}]}],'calculations':[]}
    assert not validate_research(value,e,[first,second],ContractGate(),'它们有什么关系？')['refused']
    value['paragraphs'][0]['text']='一篇提出神经网络方法，另一篇研究神经网络。'
    assert not validate_research(value,e,[first,second],ContractGate(),'它们有什么关系？')['refused']
    value['paragraphs'][0]['text']='第一篇论文研究神经网络，现有两篇摘要未确立引用关系。'
    assert not validate_research(value,e,[first,second],ContractGate(),'它们有什么关系？')['refused']
    value['paragraphs'][0]['text']='两篇存在共同主题。'
    assert not validate_research(value,e,[first,second],ContractGate(),'它们有什么关系？')['refused']
    value['paragraphs'][0]['text']='第一篇把神经网络作为研究对象。'
    assert not validate_research(value,e,[first,second],ContractGate(),'它们有什么关系？')['refused']
    for unsupported in ['第三篇论文研究神经网络。','第二篇论文研究神经网络。','这两篇论文包含两层神经网络。']:
        value['paragraphs'][0]['text']=unsupported
        with pytest.raises(PipelineError,match='数值'):validate_research(value,e,[first,second],ContractGate(),'它们有什么关系？')
    value['paragraphs'][0]['text']='这三篇论文讨论神经网络。'
    with pytest.raises(PipelineError,match='数值'):validate_research(value,e,[first,second],ContractGate(),'它们有什么关系？')
    value['paragraphs'][0]['text']='这两篇论文准确率是99.9%。'
    with pytest.raises(PipelineError,match='数值'):validate_research(value,e,[first,second],ContractGate(),'它们有什么关系？')

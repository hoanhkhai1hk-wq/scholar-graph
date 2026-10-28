import pytest

from scholar_graph.normalize import normalize
from scholar_graph.reference_identity import author_year_matcher, author_year_markers
from scholar_graph.workspace_formulas import checked_latex
from scholar_graph.errors import PipelineError
from test_validation_status import example_bundle


def test_compiled_author_year_matcher_preserves_unique_identity_and_source_order():
    base = example_bundle()['reference_entries'][0]
    refs = [{**base,'number':1,'ref_id':'a','authors':['Ada Lovelace'],'year':1843},
            {**base,'number':2,'ref_id':'b','authors':['Alan Turing','Alonzo Church'],'year':1936},
            {**base,'number':3,'ref_id':'c','authors':['A. Ambiguous'],'year':2000},
            {**base,'number':4,'ref_id':'d','authors':['B. Ambiguous'],'year':2000}]
    find = author_year_matcher(refs)
    text = 'Turing and Church, 1936; Lovelace (1843); Ambiguous (2000).'
    found = find(text)
    assert [ref['ref_id'] for ref,quote in found] == ['a','b']
    assert [quote for ref,quote in found] == ['Lovelace (1843','Turing and Church, 1936']
    assert found == author_year_markers(text,refs)
    assert not find('Lovelace (18430); Turing (1936a).')
    assert not find('No dates or matching authors here')


@pytest.mark.parametrize('title',['Attention Visualizations','Supplementary Material','Appendix A'])
def test_supplement_merged_into_figure_does_not_remain_a_reference(title):
    meta = {**example_bundle()['paper_meta'],'page_count':2}
    native = {'pages':[{'page_idx':0,'blocks':[{'type':'title','content':'References'},
                  {'type':'text','content':'[1] A. Author. Prior paper. 2020.'}]},
                {'page_idx':1,'blocks':[{'type':'image','content':title+'\nFigure 3: Original visualization.'}]}]}
    bundle = normalize(native,None,meta,[])
    assert bundle['chunks'][-1]['section_path'] == [title]
    assert 'visualization' not in bundle['reference_entries'][0]['title'].lower()


def test_ordinary_chart_title_is_not_promoted_to_supplement_heading():
    meta = {**example_bundle()['paper_meta'],'page_count':1}
    native = {'pages':[{'page_idx':0,'blocks':[{'type':'title','content':'References'},
                    {'type':'image','content':'Training Loss\nSome chart labels'}]}]}
    assert normalize(native,None,meta,[])['chunks'][-1]['section_path'] == ['References']


@pytest.mark.parametrize('value',[r'\frac{x_1}{\sqrt{d_k}}',r'\left\{x\right\}'])
def test_formula_code_keeps_source_math_syntax(value):
    assert checked_latex(value) == value


@pytest.mark.parametrize('value',['',r'\frac{x}{',r'x}',r'\input{private}',r'\href{https://example.org}{x}'])
def test_empty_unbalanced_or_nonmathematical_formula_is_not_published(value):
    with pytest.raises(PipelineError): checked_latex(value)

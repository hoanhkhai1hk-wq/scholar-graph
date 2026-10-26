"""Self-made bibliography/citation cases; official PDF acceptance is separate."""
import copy

import pytest

from scholar_graph.normalize import reference_entries, citation_links
from scholar_graph.reference_identity import (doi, arxiv, arxiv_key, parse_reference,
    title_key, resolve_reference, author_year_markers, paper_titles)
from scholar_graph.validation import ContractGate
from test_validation_status import example_bundle


@pytest.mark.parametrize('value,expected', [
    ('doi:10.5555/AbC.', '10.5555/abc'),
    ('https://doi.org/10.5555/ABC)', '10.5555/abc'),
    ('10.5555/foo(bar).', '10.5555/foo(bar)'),
    ('no identity', None),
])
def test_bare_doi_normalization(value, expected):
    assert doi(value) == expected


@pytest.mark.parametrize('value,expected', [
    ('arXiv: 1706.03762v7', '1706.03762v7'),
    ('https://arxiv.org/pdf/2205.14135v2.pdf', '2205.14135v2'),
    ('CoRR, abs/1706.03762, 2017.', '1706.03762'),
    ('arXiv:hep-th/9901001v2', 'hep-th/9901001v2'),
    ('2017. Some title', None),
])
def test_modern_legacy_arxiv_extraction(value, expected):
    assert arxiv(value) == expected


@pytest.mark.parametrize('raw', [
    'Ashish Vaswani, Noam Shazeer, and Illia Polosukhin. Attention is all you need. In NIPS, 2017.',
    'A. Vaswani, N. Shazeer, and I. Polosukhin. Attention is all you need. In NIPS, 2017.',
    'Ashish Vaswani, Noam Shazeer, and Illia Polosukhin. 2017. Attention is all you need. In NIPS.',
])
def test_title_author_initials_and_year_styles(raw):
    result = parse_reference(raw)
    assert result['title'] == 'Attention is all you need'
    assert result['authors'][-1].endswith('Polosukhin')
    assert result['year'] == 2017


def profiles(papers):
    return [{'paper': p, 'titles': [{'text': p['title'], 'source': 'PaperMeta.title', 'anchor': None}]
             if p['title'] else []} for p in papers]


def fixture():
    bundle = example_bundle()
    paper = {**bundle['paper_meta'], 'id': 'target', 'title': 'Attention: Is All You Need!',
             'doi': None, 'arxiv_id': None, 'year': 2017, 'authors': ['Ashish Vaswani']}
    ref = {**bundle['reference_entries'][0], 'title': 'attention is all you need',
           'doi': None, 'arxiv_id': None, 'year': 2017, 'authors': ['A. Vaswani']}
    return paper, ref


def test_title_ignores_punctuation_space_case_with_initial_name_auxiliary():
    paper, ref = fixture()
    result = resolve_reference(ref, profiles([paper]))
    assert result['method'] == 'title' and result['target_paper_id'] == 'target'
    assert result['evidence'][0]['shared_surnames'] == ['vaswani']
    assert title_key(paper['title']) == title_key(ref['title'])


@pytest.mark.parametrize('method', ['arxiv', 'doi'])
def test_identifier_only_match_records_method_and_basis(method):
    paper, ref = fixture()
    if method == 'arxiv':
        paper['arxiv_id'], ref['arxiv_id'] = '1706.03762v7', 'arXiv:1706.03762v1'
        assert arxiv_key(paper['arxiv_id']) == arxiv_key(ref['arxiv_id'])
    else:
        paper['doi'], ref['doi'] = '10.5555/ABC', 'https://doi.org/10.5555/abc'
    ref.update(title=None, year=None, authors=[])
    result = resolve_reference(ref, profiles([paper]))
    assert result['method'] == method and result['evidence']
    assert result['target_paper_id'] == 'target'


def test_unknown_target_identifier_can_use_exact_title_without_overriding_known_conflict():
    paper, ref = fixture()
    ref['arxiv_id'] = '1706.03762v7'
    result = resolve_reference(ref, profiles([paper]))
    assert result['method'] == 'title' and result['attempted_methods'] == ['arxiv', 'title']
    paper['arxiv_id'] = '9999.00001'
    assert resolve_reference(ref, profiles([paper]))['target_paper_id'] is None


def test_conflicting_ids_and_duplicate_versions_not_guessed():
    paper, ref = fixture()
    paper.update(arxiv_id='1706.03762v7', doi='10.5555/one')
    other = {**paper, 'id': 'other', 'arxiv_id': '9999.00001', 'doi': '10.5555/two'}
    ref.update(arxiv_id='1706.03762v1', doi='10.5555/two')
    assert resolve_reference(ref, profiles([paper, other]))['reason'] == 'conflicting_identity'
    ref['doi'] = None
    duplicate = {**paper, 'id': 'copy', 'arxiv_id': '1706.03762v3'}
    assert resolve_reference(ref, profiles([paper, duplicate]))['reason'] == 'ambiguous_identity'


def test_ambiguous_title_uses_year_but_conflicting_known_title_never_uses_author_year():
    paper, ref = fixture()
    other = {**paper, 'id': 'other', 'year': 2018}
    assert resolve_reference(ref, profiles([paper, other]))['target_paper_id'] == 'target'
    ref.update(title='An unrelated title', authors=paper['authors'])
    assert resolve_reference(ref, profiles([paper]))['target_paper_id'] is None


def test_author_year_requires_complete_names_and_uniqueness():
    paper, ref = fixture()
    ref.update(title=None, authors=paper['authors'])
    assert resolve_reference(ref, profiles([paper]))['method'] == 'author-year'
    assert resolve_reference(ref, profiles([paper, {**paper, 'id': 'other'}]))['reason'] == 'ambiguous_identity'
    ref['authors'] = ['A. Vaswani']
    assert resolve_reference(ref, profiles([paper]))['target_paper_id'] is None
    ref['authors'] = ['Someone Vaswani']
    assert resolve_reference(ref, profiles([paper]))['target_paper_id'] is None


def test_unresolved_empty_identity_is_not_a_synthetic_match():
    paper, ref = fixture()
    ref.update(title=None, authors=[], year=None)
    result = resolve_reference(ref, profiles([paper]))
    assert result['target_paper_id'] is result['method'] is None
    assert result['reason'] == 'insufficient_identity'


def test_unnumbered_bibliography_and_real_author_year_citation_links():
    b = example_bundle()
    base = b['chunks'][0]
    body = {**base, 'text': 'We use Vaswani et al. (2017) and Vaswani et al., 2017.'}
    bibliography = {**base, 'chunk_id': 'bib', 'section_path': ['References'], 'heading_1': 'References',
        'heading_2': None, 'heading_3': None,
        'text': 'Ashish Vaswani, Noam Shazeer, and Illia Polosukhin. 2017. Attention is all you need. In NIPS.'}
    b['chunks'] = [body, bibliography]
    b['reference_entries'] = reference_entries(b['chunks'], b['paper_meta']['id'])
    b['citation_links'] = citation_links(b['chunks'], b['reference_entries'])
    assert len(b['reference_entries']) == len(b['citation_links']) == 1
    assert b['reference_entries'][0]['number'] == b['citation_links'][0]['citation_number'] == 1
    assert b['citation_links'][0]['chunk_id'] == body['chunk_id']
    ContractGate().bundle(b)


def test_ambiguous_author_year_and_wrong_second_author_are_not_linked():
    _, ref = fixture()
    ref.update(authors=['Alice Smith', 'Bob Brown'], year=2020)
    assert author_year_markers('Smith and Brown (2020)', [ref])
    for text in ['Smith and Jones (2020)', 'Smith (2021)', 'Smith (2020a)']:
        assert not author_year_markers(text, [ref])
    assert not author_year_markers('Smith et al. (2020)', [ref, {**ref, 'ref_id': 'other'}])


def test_null_target_title_only_matches_whole_first_page_block_before_abstract():
    b = example_bundle()
    b['paper_meta']['title'] = None
    b['chunks'][0].update(page_number=1, section_path=[], heading_1=None, heading_2=None,
                          heading_3=None, text='Attention Is All You Need')
    before = copy.deepcopy(b)
    assert paper_titles(b)[0]['anchor']['chunk_id'] == b['chunks'][0]['chunk_id']
    assert b == before
    b['chunks'][0]['page_number'] = 2
    assert paper_titles(b) == []


def test_unstructured_reference_extracts_identifiers_without_new_fields():
    b = example_bundle()
    c = b['chunks'][0]
    c.update(section_path=['References'], heading_1='References', heading_2=None, heading_3=None,
             text='[9] Demo Author. Example Study. arXiv:1706.03762v1, 2017. doi:10.5555/ABC.')
    ref = reference_entries([c], b['paper_meta']['id'])[0]
    assert ref['arxiv_id'] == '1706.03762v1' and ref['doi'] == '10.5555/abc'
    ContractGate().record('ReferenceEntry', ref)


def test_unnumbered_reference_keeps_lowercase_cross_page_continuation():
    b = example_bundle()
    first = {**b['chunks'][0], 'section_path': ['References'],
        'text': 'Alice Smith. 2020. A title that continues'}
    second = {**first, 'chunk_id': 'continued', 'text': 'across pages. In A Venue.'}
    refs = reference_entries([first, second], b['paper_meta']['id'])
    assert len(refs) == 1
    assert refs[0]['title'] == 'A title that continues across pages'


@pytest.mark.parametrize('change', [{'year': 2018}, {'authors': ['Unrelated Person']}])
def test_known_title_with_conflicting_auxiliary_metadata_is_unresolved(change):
    paper, ref = fixture()
    paper.update(change)
    result = resolve_reference(ref, profiles([paper]))
    assert result['target_paper_id'] is None and result['reason'] == 'conflicting_auxiliary'

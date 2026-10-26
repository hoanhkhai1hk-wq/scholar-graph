import copy

from defusedxml import ElementTree as ET
import pytest

from scholar_graph.errors import PipelineError
from scholar_graph.grobid import GrobidClient, NS, authors, text
from scholar_graph.validation import ContractGate
from test_grobid_evidence import TEI
from test_validation_status import example_bundle


@pytest.mark.parametrize("xml", [None, "<title/>", "<title> \n\t </title>", "<title><hi/> </title>"])
def test_absent_empty_and_whitespace_elements_are_null(xml):
    assert text(ET.fromstring(xml) if xml else None) is None


@pytest.mark.parametrize("name,expected", [
    ('<forename>Ashish</forename><surname>Vaswani</surname>', 'Ashish Vaswani'),
    ('<forename>Geoffrey</forename><forename>E</forename><surname>Hinton</surname>', 'Geoffrey E Hinton'),
    ('<forename>Jean-Luc</forename><surname>O’Neill</surname>', 'Jean-Luc O’Neill'),
    ('Ada <surname>Lovelace</surname> Jr.', 'Ada Lovelace Jr.'),
    ('Plain Name', 'Plain Name'),
    ('<forename>Jean<hi>-</hi>Luc</forename><surname>Example</surname>', 'Jean-Luc Example'),
])
def test_person_name_component_spacing_without_splitting_inline_words(name, expected):
    root = ET.fromstring(f'<TEI xmlns="http://www.tei-c.org/ns/1.0"><author><persName>{name}</persName></author></TEI>')
    assert authors(root) == [expected]


def test_empty_preferred_title_falls_back_and_absent_header_preserves_local_metadata():
    root = ET.fromstring(TEI)
    root.find('.//t:titleStmt/t:title', NS).text = " "
    root.find('.//t:listBibl/t:biblStruct/t:analytic/t:title', NS).text = ""
    original = example_bundle()
    expected = copy.deepcopy(original)
    converted = GrobidClient('http://127.0.0.1:8070')._convert(original, root)
    assert original == expected
    assert converted['paper_meta']['title'] == expected['paper_meta']['title']
    assert converted['reference_entries'][0]['title'] == 'Test Venue'
    assert converted['reference_entries'][0]['venue'] == 'Test Venue'
    assert converted['chunks'] == expected['chunks']
    ContractGate().bundle(converted)


def test_generic_inline_text_is_preserved_and_empty_strings_still_fail_frozen_schema():
    assert text(ET.fromstring('<title>Ti<hi>k</hi>Z</title>')) == 'TikZ'
    assert authors(ET.fromstring('<TEI xmlns="http://www.tei-c.org/ns/1.0"><author><persName><forename/><surname> </surname></persName></author></TEI>')) == []
    reference = example_bundle()['reference_entries'][0]
    for field in ('title', 'venue'):
        with pytest.raises(PipelineError):
            ContractGate().record('ReferenceEntry', {**reference, field: ''})

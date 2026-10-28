import copy
import pytest
from scholar_graph.workspace_layout import checked_pages, overlap_fraction
from scholar_graph.errors import PipelineError
from scholar_graph.front_matter import local_front_matter
from test_validation_status import example_bundle


def test_model_region_coordinates_and_page_coverage_cannot_be_fabricated():
    value = [{'page_number': 3, 'regions': [{'label': 'formula', 'score': .8, 'bbox': [.1,.2,.6,.3]}]}]
    assert checked_pages(value, [3]) == value
    bad = copy.deepcopy(value); bad[0]['regions'][0]['bbox'][2] = float('nan')
    with pytest.raises(PipelineError): checked_pages(bad, [3])
    with pytest.raises(PipelineError): checked_pages(value, [1,3])
    assert overlap_fraction([.2,.2,.3,.3], [.1,.1,.6,.6]) == pytest.approx(1)
    assert overlap_fraction([.2,.2,.3,.3], [.6,.6,.8,.8]) == 0


def test_ocr_name_markers_and_separate_contact_columns_preserve_author_order():
    bundle = example_bundle(); source = bundle['chunks'][0]
    bundle['paper_meta'].update(title=None, authors=[], abstract=None)
    rows = [('A Real Research Paper', [.25,.1,.75,.13]),
            ('Alice Smith*', [.15,.2,.3,.22]), ('Bob Chen* †', [.45,.2,.6,.22]), ('Carol Jones*', [.75,.2,.9,.22]),
            ('Example University', [.45,.225,.6,.24]), ('bob@example.org', [.45,.245,.6,.26]),
            ('Abstract', [.45,.4,.6,.42]), ('Scientific prose and source findings. '*5, [.2,.45,.8,.6]), ('1 Introduction', [.2,.65,.5,.67])]
    bundle['chunks'] = [{**source,'chunk_id':f'c{i}','page_number':1,'type':'text','text':text,'bbox':box} for i,(text,box) in enumerate(rows)]
    patch, profiles, proofs = local_front_matter(bundle)
    assert patch['authors']==['Alice Smith','Bob Chen','Carol Jones']
    assert profiles[1]['institutions']==['Example University'] and profiles[0]['institutions']==[]
    assert profiles[1]['emails']==['bob@example.org']
    assert 'title' in proofs and patch['abstract'].startswith('Scientific prose')

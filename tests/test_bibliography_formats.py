from scholar_graph.normalize import citation_links, reference_entries
from scholar_graph.reference_identity import bibliography_sources
from test_validation_status import example_bundle


def example(text, path, identity):
    return {**example_bundle()['chunks'][0], 'chunk_id': identity, 'text': text,
            'section_path': path, 'heading_1': path[0] if path else None, 'heading_2': None, 'heading_3': None}


def test_author_title_year_last_is_a_reference():
    chunk = example('Sergey Ioffe and Christian Szegedy. Batch normalization: Accelerating deep network training by reducing internal covariate shift. ICML, 2015.', ['References'], 'ref')
    sources = bibliography_sources([chunk])
    assert len(sources) == 1
    refs = reference_entries([chunk], chunk['paper_id'])
    assert refs[0]['year'] == 2015 and refs[0]['authors'] == ['Sergey Ioffe', 'Christian Szegedy']


def test_symbolic_bibliography_marks_resolve_exact_body_occurrences():
    body = example('We follow [RNSS18, VSP+17]. This is not an invented [ZZ99] citation.', [], 'body')
    ref = example('[RNSS18] Alec Radford, Karthik Narasimhan, Tim Salimans, and Ilya Sutskever. Improving language understanding by generative pre-training, 2018. [VSP+17] Ashish Vaswani and Noam Shazeer. Attention is all you need. NIPS, 2017.', ['References'], 'refs')
    refs = reference_entries([body, ref], body['paper_id'])
    assert len(refs) == 2
    assert {v['citation_number'] for v in citation_links([body, ref], refs)} == {1, 2}
    assert all(v['chunk_id'] == 'body' for v in citation_links([body, ref], refs))

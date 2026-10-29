"""Regression for code displaced as a PDF column; synthetic sources only."""
import ast
import copy
import re

import pytest

from scholar_graph.code_layout import repair_page, code_ranges, join_code
from scholar_graph.translation import Translator, render_markdown
from test_translation import gateway
from test_validation_status import example_bundle
from scholar_graph.validation import ContractGate
from scholar_graph.errors import PipelineError
from scholar_graph.workspace_translation import validated_chinese_task

CODE = '```python\ndef forward(x):\n    # Keep this English comment.\n    return x + 1\n```'


def fixture():
    bundle = example_bundle()
    template = bundle['chunks'][0]
    specs = [('open', '$f(x) = x^2 + 1$ ```python', .2, .1),
             ('def', 'def forward(x):', .24, .1),
             ('comment', '# Keep this English comment.', .26, .14),
             ('close', '```', .3, .1),
             ('return', 'return x + 1', .28, .14)]
    bundle['chunks'] = [{**template, 'chunk_id': cid, 'text': text,
                         'bbox': [x, y, .45, y + .01]} for cid, text, y, x in specs]
    bundle['reference_entries'] = bundle['citation_links'] = []
    return bundle


def test_exact_pdf_region_repairs_order_indent_and_keeps_ids_and_geometry():
    original = fixture()['chunks']
    before = copy.deepcopy(original)
    fixed, changes = repair_page(original, CODE)
    assert original == before
    assert [c['chunk_id'] for c in fixed] == ['open', 'def', 'comment', 'return', 'close']
    assert join_code([c['text'] for c in fixed]) == '$f(x) = x^2 + 1$\n' + CODE
    assert {c['chunk_id']: c['bbox'] for c in fixed} == {c['chunk_id']: c['bbox'] for c in original}
    assert len(changes) == 1
    assert repair_page(fixed, CODE)[0] == fixed


@pytest.mark.parametrize('damage', ['extra_character', 'missing_character', 'unclosed', 'other_column'])
def test_ambiguous_or_unmatched_source_never_guesses(damage):
    original = fixture()['chunks']
    source = CODE
    if damage == 'extra_character':
        source = source.replace('x + 1', 'x + 2')
    elif damage == 'missing_character':
        source = source.replace('    return x + 1\n', '')
    elif damage == 'unclosed':
        source = source[:-3]
    else:
        original.append({**original[1], 'chunk_id': 'right-column', 'text': 'Unrelated prose', 'bbox': [.6, .25, .9, .26]})
    fixed, changes = repair_page(original, source)
    assert fixed == original
    assert changes == []


def test_prose_columns_tables_and_plain_backticks_keep_their_order():
    chunks = fixture()['chunks']
    chunks[0]['text'] = 'Prose about `code`.'
    chunks[3]['text'] = 'Another paragraph.'
    assert repair_page(chunks, 'Two columns without a complete fence')[0] == chunks
    assert code_ranges(chunks) == {}


@pytest.mark.parametrize('marker', ['```', '~~~~'])
def test_full_code_chunk_and_fence_types(marker):
    chunk = fixture()['chunks'][0]
    code = CODE.replace('```', marker)
    chunk['text'] = code.replace('\n', ' ')
    fixed, changes = repair_page([chunk], code)
    assert fixed[0]['text'] == code
    assert len(changes) == 1


def test_export_has_no_html_inside_code_and_python_is_executable():
    bundle = fixture()
    bundle['chunks'], _ = repair_page(bundle['chunks'], CODE)
    segments = [{'source_chunk_id': c['chunk_id'], 'source_text': c['text'], 'translated_text': c['text']} for c in bundle['chunks']]
    markdown = render_markdown(bundle, segments)
    body = re.search(r'```python\n(.*?)\n```', markdown, re.S)[1]
    assert '<a ' not in body
    assert body == CODE.split('\n', 1)[1].rsplit('\n', 1)[0]
    ast.parse(body)
    namespace = {}
    # Authored deterministic sample only; never execute arbitrary uploaded code.
    exec(compile(body, '<authored-code-test>', 'exec'), namespace)
    assert namespace['forward'](2) == 3
    assert all(markdown.index(f'<a id="{c["chunk_id"]}"></a>') < markdown.index('```python') for c in bundle['chunks'])


def test_translation_does_not_send_fragmented_code_or_comments_to_model(monkeypatch):
    bundle = fixture()
    bundle['chunks'], _ = repair_page(bundle['chunks'], CODE)
    template = bundle['chunks'][0]
    bundle['chunks'].insert(0, {**template, 'chunk_id': 'prose', 'text': 'The encoder uses attention.'})
    client, calls = gateway(monkeypatch)
    class Repository:
        gate = ContractGate()
        def paper(self, _):
            return bundle
    response = Translator(Repository(), client).translate(bundle['paper_meta']['id'], scope='full')
    assert len(calls) == 1
    assert not any('forward' in str(call['items']) or 'English comment' in str(call['items']) for call in calls)
    translated = {s['source_chunk_id']: s['translated_text'] for s in response['segments']}
    assert all(translated[c['chunk_id']] == c['text'] for c in bundle['chunks'][1:])
    assert '译文' in translated['prose']


def test_code_context_can_cross_a_translation_batch_boundary(monkeypatch):
    bundle = fixture()
    bundle['chunks'], _ = repair_page(bundle['chunks'], CODE)
    spans = code_ranges(bundle['chunks'])
    selected = bundle['chunks'][2:4]
    client, calls = gateway(monkeypatch)
    class Repository:
        gate = ContractGate()
        def paper(self, _):
            return {**bundle, 'chunks': selected}
    result = Translator(Repository(), client, code_spans=spans).translate(bundle['paper_meta']['id'], scope='full')
    assert calls == []
    assert [s['translated_text'] for s in result['segments']] == [c['text'] for c in selected]


def test_historical_code_translation_cannot_be_relabelled_or_reused_as_verified():
    value = {'status': 'completed', 'result': {'translation': {'paper_id': 'p', 'target': 'zh', 'scope': 'full',
             'metadata': {'complete': True}, 'segments': [{'source_chunk_id': 'a', 'source_text': CODE}]}}}
    with pytest.raises(PipelineError, match='旧版代码布局'):
        validated_chinese_task(value, 'p', 'full', ['a'])

"""Alignment mathematics; browser/native-input acceptance is recorded separately."""
import json
from pathlib import Path
import subprocess
from scholar_graph.translation import protect,restore,select_chunks
from test_validation_status import example_bundle
import copy
import pytest
from scholar_graph.workspace_translation import validated_chinese_task
from scholar_graph.errors import PipelineError


def test_paragraph_progress_is_monotonic_reversible_and_bounded():
    root=Path(__file__).resolve().parents[1]
    result=subprocess.run(['node','tests/item03/check_scroll.cjs'],cwd=root,capture_output=True,text=True,check=True)
    value=json.loads(result.stdout)
    assert value['passed'] and value['checks']>=200


def test_html_code_and_math_bodies_are_opaque_not_only_their_tags():
    source='<pre><code>print("Never translate this literal")\n# Keep English</code></pre> and <math>softmax(x)</math>'
    masked,spans=protect(source)
    assert 'Never translate' not in masked and 'Keep English' not in masked and 'softmax' not in masked
    assert restore(masked,spans)==source


def test_abstract_exact_source_body_excludes_mislabelled_footer_and_author_notes():
    bundle=example_bundle(); body=bundle['chunks'][0]
    body.update(section_path=['Abstract'],heading_1='Abstract',heading_2=None)
    bundle['paper_meta']['abstract']=body['text']
    footer=copy.deepcopy(body); footer.update(chunk_id='author-notes',text='Equal contribution. Work performed while at Google Brain.')
    bundle['chunks'].append(footer)
    assert select_chunks(bundle,'abstract')==[body]
    bundle['paper_meta']['abstract']=None
    assert select_chunks(bundle,'abstract')==[body,footer]


def test_full_reverse_translation_requires_completed_full_source_not_abstract_or_partial():
    value={'status':'completed','result':{'translation':{'paper_id':'p','target':'zh','scope':'full',
            'metadata':{'complete':True},'segments':[{'source_chunk_id':'a'},{'source_chunk_id':'b'}]}}}
    assert validated_chinese_task(value,'p','full',['a','b'])
    for damage in ['abstract','partial','incomplete','reordered','missing']:
        task=copy.deepcopy(value);t=task['result']['translation']
        if damage=='abstract': t['scope']='abstract'
        if damage=='partial': task['status']='partial'
        if damage=='incomplete': t['metadata']['complete']=False
        if damage=='reordered': t['segments'].reverse()
        if damage=='missing': t['segments'].pop()
        with pytest.raises(PipelineError): validated_chinese_task(task,'p','full',['a','b'])

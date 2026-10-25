import json

import httpx
import pytest

from scholar_graph.deepseek_client import DeepSeekClient
from scholar_graph.errors import PipelineError
from scholar_graph.grounded_model import GroundedModelAnswerer, accepted_record, evidence_candidates, layout_author_order
from scholar_graph.validation import ContractGate
from test_validation_status import example_bundle


def response(message, *, status=200):
    return httpx.Response(status, json={'choices': [{'finish_reason': 'tool_calls' if message.get('tool_calls') else 'stop', 'message': message}],
                                       'usage': {'prompt_tokens': 10, 'completion_tokens': 5, 'total_tokens': 15}})


def test_model_answer_preserves_real_quotes_anchors_and_tokens():
    bundle = example_bundle()
    def handle(request):
        body = json.loads(request.content)
        payload = json.loads(body['messages'][-1]['content'])
        item = payload['evidence'][0]
        assert body['thinking'] == {'type': 'disabled'}
        return response({'content': json.dumps({'answers': [{'paper_id': bundle['paper_meta']['id'], 'refused': False,
            'claims': [{'evidence_id': item['evidence_id'], 'quote': item['quote']}]}]})})
    client = DeepSeekClient(key='unit-sentinel-not-real', model='deepseek-mock', transport=httpx.MockTransport(handle))
    record, evidence = GroundedModelAnswerer(ContractGate(), client).answer(bundle, 'How many samples?')
    assert not record['refused'] and record['numeric_fact_check']['status'] == 'passed'
    assert record['anchors'] == [evidence[0]['anchor']]
    assert client.calls[0]['total_tokens'] == 15
    assert 'unit-sentinel' not in json.dumps(client.calls) + repr(client)


@pytest.mark.parametrize('status', [401, 429, 500, 302])
def test_upstream_bodies_and_headers_never_escape(status):
    def handle(request):
        return httpx.Response(status, text='unit-sensitive-body', headers={'Location': 'https://untrusted.invalid/'})
    client = DeepSeekClient(key='unit-private-value', model='deepseek-mock', transport=httpx.MockTransport(handle))
    with pytest.raises(PipelineError) as error:
        client.complete([{'role': 'user', 'content': 'unit-request-body'}], phase='qa')
    assert error.value.code == 'UPSTREAM_ERROR'
    serialized = json.dumps(error.value.envelope()) + json.dumps(client.calls) + repr(client)
    assert all(s not in serialized for s in ('unit-private-value', 'unit-sensitive-body', 'unit-request-body', 'untrusted.invalid'))


def test_nonliteral_claim_is_rejected_and_named_beta_conflict_refuses():
    bundle = example_bundle()
    bundle['chunks'][0]['text'] = 'Adam uses β1 = 0.9 and β2 = 0.98.'
    gate = ContractGate()
    candidates = evidence_candidates(bundle, 'Adam β1 β2')
    proposal = {'paper_id': bundle['paper_meta']['id'], 'refused': False,
                'claims': [{'evidence_id': candidates[0]['evidence_id'], 'quote': 'Adam uses β1 = 0.5.'}]}
    with pytest.raises(PipelineError):
        accepted_record(bundle, proposal, candidates, gate)
    proposal['claims'][0]['quote'] = candidates[0]['quote']
    value, _ = accepted_record(bundle, proposal, candidates, gate, question='Adam的β₁=0.5、β₂=0.6，对吗？')
    assert value['refused'] and value['numeric_fact_check']['status'] == 'failed'
    assert value['numeric_fact_check']['checks'][0]['evidence']


def test_repeated_chunk_quotes_merge_only_as_contiguous_source_span():
    bundle = example_bundle()
    bundle['chunks'][0]['text'] = 'First source sentence. Second source sentence.'
    candidates = evidence_candidates(bundle, 'source sentence')
    eid = candidates[0]['evidence_id']
    proposal = {'paper_id': bundle['paper_meta']['id'], 'refused': False,
                'claims': [{'evidence_id': eid, 'quote': 'First source sentence.'}, {'evidence_id': eid, 'quote': 'Second source sentence.'}]}
    value, evidence = accepted_record(bundle, proposal, candidates, ContractGate())
    assert len(value['anchors']) == 1 and evidence[0]['quote'] == bundle['chunks'][0]['text']


def test_author_contacts_are_ordered_by_layout_rows_not_parser_columns():
    import copy
    bundle = example_bundle()
    template = bundle['chunks'][0]
    bundle['chunks'] = []
    for col, names in enumerate((('Alpha One', 'Gamma Three'), ('Beta Two', 'Delta Four'))):
        chunk = copy.deepcopy(template)
        chunk.update(chunk_id='column-' + str(col), page_number=1, bbox=[.1 + col * .4, .1, .4 + col * .4, .3],
                     text=f'{names[0]} ∗ Institute A first{col}@example.org {names[1]} ∗ Institute B second{col}@example.org')
        bundle['chunks'].append(chunk)
    assert [x['name'] for x in layout_author_order(bundle)] == ['Alpha One', 'Beta Two', 'Gamma Three', 'Delta Four']


def test_wrong_ordinal_author_quote_is_retried_before_return():
    bundle = example_bundle()
    chunk = bundle['chunks'][0]
    chunk.update(page_number=1, bbox=[.1, .1, .4, .3],
                 text='Alpha One ∗ Institute A alpha@example.org Gamma Three ∗ Institute B gamma@example.org')
    seen = []
    def handle(request):
        payload = json.loads(json.loads(request.content)['messages'][-1]['content'])
        seen.append(payload)
        item = next(e for e in payload['evidence'] if e['anchor']['chunk_id'] == chunk['chunk_id'])
        quote = 'Alpha One ∗ Institute A' if len(seen) == 1 else 'Gamma Three ∗ Institute B'
        return response({'content': json.dumps({'answers': [{'paper_id': bundle['paper_meta']['id'], 'refused': False,
            'claims': [{'evidence_id': item['evidence_id'], 'quote': quote}]}]})})
    client = DeepSeekClient(key='unit-sentinel-not-real', model='deepseek-mock', transport=httpx.MockTransport(handle))
    value, _ = GroundedModelAnswerer(ContractGate(), client).answer(bundle, '第2作者是谁、机构是什么？')
    assert len(seen) == 2 and 'validation_feedback' in seen[1]
    assert 'Gamma Three' in value['answer'] and 'Alpha One' not in value['answer']

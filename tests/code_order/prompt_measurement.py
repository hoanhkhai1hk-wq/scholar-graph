"""A protocol-only before/after probe; NEVER count this as a live model test."""
import json
import subprocess
import sys
import types
import httpx
from common import ROOT, BASE, write

sys.path[:0] = [str(ROOT / 'backend'), str(ROOT / 'tests')]
from scholar_graph.deepseek_client import DeepSeekClient
from scholar_graph.translation import Translator
from scholar_graph.code_layout import repair_page
from scholar_graph.validation import ContractGate
from scholar_graph.errors import PipelineError
from test_code_layout import fixture, CODE

if __name__ == '__main__':
    before = types.ModuleType('scholar_graph._before_code_translation')
    before.__package__ = 'scholar_graph'
    source = subprocess.check_output(['git', 'show', 'b930bbd257824e960cf829560d77dd58fd06bbdf:backend/scholar_graph/translation.py'], cwd=ROOT).decode('utf8')
    exec(compile(source, '<previous-committed-translator>', 'exec'), before.__dict__)
    result = {'evidence_type': 'protocol_mock_only_not_live_model', 'before_commit': 'b930bbd257824e960cf829560d77dd58fd06bbdf'}
    for name, translator in [('before', before.Translator), ('after', Translator)]:
        bundle = fixture()
        if name == 'after':
            bundle['chunks'], _ = repair_page(bundle['chunks'], CODE)
        payloads = []
        def response(request):
            payload = json.loads(json.loads(request.content)['messages'][-1]['content'])
            payloads.append(payload)
            content = json.dumps({'translations': [{'id': item['id'], 'text': item['text']} for item in payload['items']], 'terminology': []})
            return httpx.Response(200, json={'choices': [{'finish_reason': 'stop', 'message': {'role': 'assistant', 'content': content}}]})
        client = DeepSeekClient(key='protocol-probe-only', model='mock-not-live', transport=httpx.MockTransport(response))
        class Repository:
            gate = ContractGate()
            def paper(self, _):
                return bundle
        status, reason = 'completed', None
        try:
            translator(Repository(), client).translate(bundle['paper_meta']['id'], scope='full')
        except PipelineError as error:
            status, reason = 'validation_rejected', error.details
        # Count the first payload once; retries are separately recorded.
        items = payloads[0]['items'] if payloads else []
        result[name] = {'code_only_prompt_items': len(items), 'code_only_prompt_chars': sum(len(item['text']) for item in items),
                        'mock_requests': len(payloads), 'mock_result': status, 'mock_rejection': reason}
    assert result['before']['code_only_prompt_items'] > 0 and result['after']['code_only_prompt_items'] == 0
    write(BASE / 'prompt-measurement.json', result)
    print(json.dumps(result))

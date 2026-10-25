import pytest

from scholar_graph.deepseek_client import DeepSeekClient, json_content


@pytest.mark.real_model
def test_real_deepseek_connectivity_without_body_logging(request):
    client = DeepSeekClient.environment()
    message = client.complete([{'role': 'system', 'content': 'Return JSON only.'},
                               {'role': 'user', 'content': 'Return {"ok":true}.'}], phase='live_test')
    assert json_content(message).get('ok') is True
    assert client.calls[-1]['status'] == 'succeeded'
    # JUnit stores only the gateway's allowlisted metadata, never protocol bodies.
    request.node.user_properties.extend(('deepseek_' + name, str(value)) for name, value in client.calls[-1].items())

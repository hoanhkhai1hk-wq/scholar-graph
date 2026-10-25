"""Real official-paper QA. Persist only accepted answers/anchors and allowlisted metadata."""
import json
import os
import sys
from decimal import Decimal
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))
from fastapi.testclient import TestClient
from scholar_graph.api import create_app
from scholar_graph.validation import ContractGate
from scholar_graph.qa_evidence import numbers

QUESTIONS = [
    '论文Attention Is All You Need的第6作者是谁，在哪个公司/机构工作？',
    '其中Adam优化器的超参数β₁和β₂分别被设置为了多少？',
    '这篇论文中提到的Transformer架构，在训练Base模型时使用了多少个GPU？具体是什么型号？',
    'Transformer (big)模型在English-to-German任务上的BLEU分数是多少？当时的State-of-the-art模型是多少？提升了多少？',
    '请列出论文中引用的关于“Layer Normalization”的参考文献（References）的完整作者和年份。',
    '根据《Attention Is All You Need》和《BERT: Pre-training of Deep Bidirectional Transformers for Language Understanding》。请对比：BERT的架构和原始Transformer的Encoder有什么承袭关系？BERT丢弃了原始Transformer的哪个部分？',
]
REFUSAL = '论文用Adam的β₁=0.5、β₂=0.6进行训练，对吗？请确认。'


def persist(path, value):
    # A final in-memory check prevents accidental credentials in ANY saved report.
    raw = json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False)
    key = os.environ.get('DEEPSEEK_API_KEY')
    if key and key in raw:
        raise RuntimeError('Refused to persist credential-containing output')
    path.write_text(raw + '\n', encoding='utf-8')


def author_guard_check():
    """Recheck just the final ordinal guard without replacing earlier six-case evidence."""
    ids = json.loads((ROOT / 'data/real-model/sources.json').read_text(encoding='utf-8'))
    with TestClient(create_app(data_dir=ROOT / 'data/real-model/records'), raise_server_exceptions=False) as client:
        response = client.post(f'/api/v1/papers/{ids["attention_id"]}/qa', json={'question': QUESTIONS[0]})
    value = response.json()
    metadata = json.loads(unquote(response.headers.get('X-ScholarGraph-QA-Meta', '%7B%7D')))
    passed = response.status_code == 200 and not value.get('refused', True) and all(
        word in value.get('answer', '').casefold() for word in ('aidan', 'toronto'))
    if response.status_code == 200:
        ContractGate().record('QAAnswer', value)
    persist(ROOT / 'tests/reports/real-model-final-author-check.json', {
        'scope': '官方 pdf/ 真文件；最终作者序号门禁补验，不覆盖六题历史结果',
        'question': QUESTIONS[0], 'http_status': response.status_code, 'result': value,
        'metadata': metadata, 'passed': passed})
    print(json.dumps({'author_guard_final_check_passed': passed, 'model_calls': metadata.get('model_calls', [])}))


def main():
    folder = ROOT / 'tests/reports'
    report = folder / 'real-model-orchestration-results.json'
    ids = json.loads((ROOT / 'data/real-model/sources.json').read_text(encoding='utf-8'))
    app = create_app(data_dir=ROOT / 'data/real-model/records')
    result = {'scope': '官方 pdf/ 真文件；题面来自本地命题PDF，仅规范空格与β下标',
              'environment': {name: '已设置' if os.environ.get(name) else '未设置'
                              for name in ('SCHOLAR_GRAPH_QA_MODE', 'DEEPSEEK_MODEL', 'DEEPSEEK_API_KEY')},
              'cases': [], 'raw_model_bodies_retained': False, 'external_tracing': False}
    needles = [('aidan', 'toronto'), ('0.9', '0.98'), ('8', 'p100'), ('28.4', '26.36'), ('ba', 'kiros', 'hinton', '2016')]
    gate = ContractGate()
    with TestClient(app, raise_server_exceptions=False) as client:
        for n, question in enumerate(QUESTIONS):
            multi = n == 5
            path = '/api/v1/compare' if multi else f'/api/v1/papers/{ids["attention_id"]}/qa'
            body = {'question': question, **({'paper_ids': [ids['attention_id'], ids['bert_id']]} if multi else {})}
            response = client.post(path, json=body)
            meta = json.loads(unquote(response.headers.get('X-ScholarGraph-QA-Meta', '%7B%7D')))
            value = response.json()
            row = {'case': n + 1, 'question': question, 'http_status': response.status_code, 'metadata': meta, 'passed': False}
            if response.status_code == 200:
                records = value['per_paper'] if multi else [value]
                for record in records:
                    gate.record('QAAnswer', record)
                row['result'] = value
                text = ' '.join(r['answer'] for r in records).casefold()
                if multi:
                    checks = {'encoder': 'encoder' in text, 'bidirectional': 'bidirectional' in text,
                              'decoder_source': 'decoder' in text or 'encoder stack' in text,
                              'vaswani_source': 'vaswani' in text, 'both_supported': all(not r['refused'] and r['anchors'] for r in records)}
                else:
                    checks = {needle: needle in text for needle in needles[n]}
                    checks['not_refused'] = not value['refused']
                    checks['anchors_present'] = bool(value['anchors'])
                    if n in (1, 2, 3):
                        checks['numeric_backtrace'] = value['numeric_fact_check']['status'] == 'passed'
                    if n == 3 and all(checks.values()):
                        row['derived_numeric_check'] = {'expression': '28.4 - 26.36',
                            'value': str(Decimal('28.4') - Decimal('26.36')), 'unit': 'BLEU',
                            'source': '两项数值均在已通过原文锚点校验的回答中；差值由代码计算，不冒充原文逐字陈述。',
                            'anchors': value['anchors']}
                row['verification'] = checks
                row['passed'] = all(checks.values()) and bool(meta.get('model_calls'))
            else:
                # Backend exposes only stable sanitized errors; never save upstream bodies.
                row['error'] = value if set(value) == {'error_code', 'message', 'details'} else {'error_code': 'INTERNAL_ERROR'}
            result['cases'].append(row)
            persist(report, result)
            print(json.dumps({'case': n + 1, 'http_status': response.status_code, 'passed': row['passed'], 'calls': meta.get('model_calls', [])}, ensure_ascii=False), flush=True)
        refusal_response = client.post(f'/api/v1/papers/{ids["attention_id"]}/qa', json={'question': REFUSAL})
        result['refusal'] = {'question': REFUSAL, 'http_status': refusal_response.status_code,
            'result': refusal_response.json(), 'metadata': json.loads(unquote(refusal_response.headers.get('X-ScholarGraph-QA-Meta', '%7B%7D'))),
            'passed': refusal_response.status_code == 200 and refusal_response.json().get('refused') is True}
        response = client.post('/api/v1/compare?agent=true', json={'question': QUESTIONS[5], 'paper_ids': [ids['attention_id'], ids['bert_id']]})
        metadata = json.loads(unquote(response.headers.get('X-ScholarGraph-Agent-Meta', '%7B%7D')))
        result['orchestration'] = {'http_status': response.status_code, 'result': response.json(), 'metadata': metadata,
            'passed': response.status_code == 200 and metadata.get('fallback_reason') is None and metadata.get('validated') is True
                      and any(c['tool_name'] == 'search' and c['status'] == 'succeeded' for c in metadata.get('tool_calls', []))
                      and all(not r['refused'] for r in response.json().get('per_paper', []))}
        persist(report, result)
        print(json.dumps({'refusal_passed': result['refusal']['passed'], 'orchestration_passed': result['orchestration']['passed'],
                          'trace': metadata.get('trace'), 'tool_calls': metadata.get('tool_calls'), 'model_calls': metadata.get('model_calls')}, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    if sys.argv[1:] == ['--author-guard-only']:
        author_guard_check()
    elif sys.argv[1:]:
        raise SystemExit('Only --author-guard-only is supported; default runs all cases.')
    else:
        main()

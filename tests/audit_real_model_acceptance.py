"""Audit approved answers and safe metadata against local official records, without model calls."""
import hashlib
import json
import os
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))
from scholar_graph.api_repository import ApiRepository
from scholar_graph.grounded_model import layout_author_order
from scholar_graph.qa import MISSING, PREMISE, validate_answer
from scholar_graph.qa_compare import validate_comparison
from scholar_graph.validation import ContractGate

BASELINE = '4f6ae8cbb5959e061cad292a394a8879e33abc73'
REPORTS = ROOT / 'tests/reports'
MODEL_FIELDS = {'provider', 'model', 'phase', 'elapsed_seconds', 'prompt_tokens', 'completion_tokens',
                'total_tokens', 'http_status', 'status'}


def require(value, reason):
    if not value:
        raise RuntimeError(reason)


def load(name):
    return json.loads((REPORTS / name).read_text(encoding='utf-8'))


def git(*args):
    return subprocess.check_output(['git', *args], cwd=ROOT, text=True, encoding='utf-8').strip()


def checked_calls(value):
    calls = []
    for row in value.get('cases', []):
        calls.extend(row.get('metadata', {}).get('model_calls', []))
    for name in ('refusal', 'orchestration'):
        calls.extend(value.get(name, {}).get('metadata', {}).get('model_calls', []))
    if 'cases' not in value and 'metadata' in value:
        calls.extend(value['metadata'].get('model_calls', []))
    for call in calls:
        require(set(call) == MODEL_FIELDS, 'Model metadata contains unexpected fields')
        require(call['provider'] == 'deepseek' and call['http_status'] == 200 and call['status'] == 'succeeded',
                'A saved call is not a successful real-provider call')
        require(call['prompt_tokens'] + call['completion_tokens'] == call['total_tokens'], 'Token totals disagree')
    return calls


def main():
    gate = ContractGate()
    repo = ApiRepository(ROOT / 'data/real-model/records', gate)
    sources = json.loads((ROOT / 'data/real-model/sources.json').read_text(encoding='utf-8'))
    ids = [sources['attention_id'], sources['bert_id']]
    bundles = [repo.paper(pid) for pid in ids]
    sources_audit = []
    for bundle, filename in zip(bundles, ('pdf/1706.03762v7.pdf', 'pdf/N19-1423.pdf'), strict=True):
        gate.bundle(bundle)
        digest = hashlib.sha256((ROOT / filename).read_bytes()).hexdigest()
        require(bundle['paper_meta']['id'] == 'paper-' + digest, 'Official PDF hash disagrees with source record')
        sources_audit.append({'file': filename, 'paper_id': bundle['paper_meta']['id'], 'sha256': digest,
                              'pages': bundle['paper_meta']['page_count'], 'chunks': len(bundle['chunks'])})

    final = load('real-model-orchestration-results.json')
    require(len(final['cases']) == 6 and all(row['passed'] for row in final['cases']), 'Six-question acceptance incomplete')
    require(final['refusal']['passed'] and final['orchestration']['passed'], 'Refusal or real graph acceptance failed')
    require(not final['raw_model_bodies_retained'] and not final['external_tracing'], 'Unexpected body retention')
    approved = []

    def single(record):
        paper_id = record['anchors'][0]['paper_id'] if record['anchors'] else ids[0]
        bundle = bundles[ids.index(paper_id)]
        prefix = next((s for s in (MISSING, PREMISE) if record['answer'].startswith(s)), '')
        body = record['answer'][len(prefix):].removeprefix('\n\n') if prefix else record['answer']
        blocks = re.split(r'\n\n(?=【证据 [A-Z]】\n)', body) if body else []
        quotes = [block.split('\n', 1)[1] for block in blocks]
        require(len(quotes) == len(record['anchors']), 'Answer quote/anchor cardinality mismatch')
        evidence = [{'anchor': a, 'quote': q} for a, q in zip(record['anchors'], quotes, strict=True)]
        validate_answer(record, bundle, evidence, gate, prefix=prefix)
        approved.append(record)

    for row in final['cases']:
        if row['case'] == 6:
            validate_comparison(row['result'], bundles, gate)
            approved.extend(row['result']['per_paper'])
        else:
            single(row['result'])
    single(final['refusal']['result'])
    validate_comparison(final['orchestration']['result'], bundles, gate)
    approved.extend(final['orchestration']['result']['per_paper'])
    author_check = load('real-model-final-author-check.json')
    require(author_check['passed'], 'Final ordinal guard live check failed')
    single(author_check['result'])
    author = next(row for row in layout_author_order(bundles[0]) if row['ordinal'] == 6)
    require(author['name'] == 'Aidan N. Gomez' and 'University of Toronto' in author['affiliation'], 'Author layout source mismatch')
    require(author['name'] in final['cases'][0]['result']['answer'], 'Sixth author answer disagrees with layout')
    difference = final['cases'][3]['derived_numeric_check']
    require(Decimal(difference['value']) == Decimal('28.4') - Decimal('26.36'), 'BLEU subtraction incorrect')
    texts = [r['answer'] for r in final['cases'][5]['result']['per_paper']]
    require('encoder and decoder' in texts[0] and 'bidirectional Transformer encoder' in texts[1]
            and 'Vaswani et al. (2017)' in texts[1], 'Comparison lacks architecture inheritance source facts')
    require(final['refusal']['result']['refused'] and final['refusal']['result']['numeric_fact_check']['status']
            in ('failed', 'unverifiable'), 'Wrong beta premise was incorrectly accepted or marked verified')

    meta = final['orchestration']['metadata']
    require(meta['engine'] == 'langgraph' and meta['max_attempts'] == 3 and meta['attempts'] <= 3,
            'Graph retry budget inconsistent')
    require(meta['fallback_reason'] is None and meta['validated'] and not meta['checkpointing'] and not meta['external_tracing'],
            'Final graph was fallback or failed')
    validations = [row['validation'] for row in meta['trace'] if row['node'] == 'validate']
    require(validations == [False, False, True], 'Saved live graph does not show two real rejection/retrieval cycles')
    for tool in meta['tool_calls']:
        require(tool['origin'] == 'model_function_call' and tool['tool_name'] == 'search' and tool['status'] == 'succeeded',
                'Unexpected tool origin or result')
        require(set(tool['arguments_summary']) == {'paper_ids', 'query_chars', 'limit'}, 'Raw tool arguments retained')
        require(set(tool['arguments_summary']['paper_ids']).issubset(ids), 'Tool queried unrelated papers')
        require(tool['return_summary']['evidence_count'] > 0 and tool['return_summary']['method'] == 'lexical', 'Search proof missing')

    junit = ET.parse(REPORTS / 'real-model-orchestration-pytest.xml').getroot()
    suites = list(junit.iter('testsuite'))
    totals = {name: sum(int(s.attrib[name]) for s in suites) for name in ('tests', 'failures', 'errors', 'skipped')}
    require(totals == {'tests': 326, 'failures': 0, 'errors': 0, 'skipped': 0}, 'Full regression not fully passing')
    no_key_suites = list(ET.parse(REPORTS / 'real-model-no-key-pytest.xml').getroot().iter('testsuite'))
    require(sum(int(s.attrib['skipped']) for s in no_key_suites) == 1
            and all(s.attrib['failures'] == s.attrib['errors'] == '0' for s in no_key_suites), 'No-key test must skip')
    live = next(c for c in junit.iter('testcase') if c.attrib['name'] == 'test_real_deepseek_connectivity_without_body_logging')
    properties = {p.attrib['name'].removeprefix('deepseek_'): p.attrib['value'] for p in live.findall('./properties/property')}
    live_meta = {k: int(properties[k]) if k in ('http_status', 'prompt_tokens', 'completion_tokens', 'total_tokens') else
                 float(properties[k]) if k == 'elapsed_seconds' else properties[k] for k in MODEL_FIELDS}
    checked_calls({'metadata': {'model_calls': [live_meta]}})
    current_calls = checked_calls(final) + checked_calls(author_check) + [live_meta]
    histories = []
    historical_calls = []
    for path in sorted(REPORTS.glob('real-model-orchestration-attempt-*.json')):
        value = load(path.name)
        historical_calls.extend(checked_calls(value))
        histories.append({'file': path.name, 'passed': sum(r['passed'] for r in value['cases']), 'total': len(value['cases']),
                          'refusal_passed': value['refusal']['passed'], 'agent_passed': value['orchestration']['passed']})

    def summary(calls):
        return {'calls': len(calls), 'providers': sorted({c['provider'] for c in calls}),
                'requested_models': sorted({c['model'] for c in calls}),
                'elapsed_seconds_sum': round(sum(c['elapsed_seconds'] for c in calls), 6),
                **{k: sum(c[k] for c in calls) for k in ('prompt_tokens', 'completion_tokens', 'total_tokens')}}

    unchanged = ['contracts', 'frontend', 'prompts', 'experiments', 'test-records']
    require(not git('diff', '--name-only', BASELINE, '--', *unchanged), 'Out-of-scope or frozen file changed')
    require(not git('ls-files', 'pdf'), 'Local corpus is tracked')
    require('/pdf/' in (ROOT / '.gitignore').read_text(encoding='utf-8').splitlines(), 'pdf directory not explicitly ignored')
    changed = set(git('diff', '--name-only', BASELINE).splitlines()) | set(git('ls-files', '--others', '--exclude-standard').splitlines())
    key = os.environ.get('DEEPSEEK_API_KEY')
    require(bool(key), 'Credential safety check requires injected environment; key value is never reported')
    for name in changed:
        path = ROOT / name
        if path.is_file():
            require(key.encode() not in path.read_bytes(), 'Credential safety check rejected a deliverable; value withheld')

    audit = {'scope': '官方 pdf/ 真文件；只审计已批准答案、锚点与允许的调用元数据，不含原始模型协议正文',
             'baseline_main': BASELINE, 'sources': sources_audit, 'six_cases_passed': 6,
             'validated_qa_records': len(approved), 'validated_anchor_occurrences': sum(len(r['anchors']) for r in approved),
             'wrong_premise_refused': True, 'live_validation_sequence': validations,
             'actual_model_tool_calls': len(meta['tool_calls']), 'full_regression': totals,
             'no_key_live_test_skipped': 1, 'current_retained_calls': summary(current_calls),
             'historical_retained_calls': summary(historical_calls),
             'metadata_scope_note': '只合计报告/JUnit中保留的调用；初次连通42token另记，早期422未带回调用元数据，不冒充账单总额。',
             'historical_attempts': histories, 'unchanged_directories': unchanged,
             'corpus_ignored_and_untracked': True, 'key_scan': '已检查全部本单交付文件，未检出；不记录Key值',
             'environment': {name: '已设置' if os.environ.get(name) else '未设置' for name in
                             ('SCHOLAR_GRAPH_QA_MODE', 'DEEPSEEK_MODEL', 'DEEPSEEK_API_KEY')},
             'status': 'passed'}
    raw = json.dumps(audit, ensure_ascii=False, indent=2) + '\n'
    require(key not in raw, 'Audit credential safety check rejected output')
    (REPORTS / 'real-model-orchestration-audit.json').write_text(raw, encoding='utf-8')
    print(json.dumps({'audit': audit['status'], 'cases_passed': 6, 'full_regression': totals,
                      'current_retained_calls': audit['current_retained_calls']}, ensure_ascii=False))


if __name__ == '__main__':
    main()

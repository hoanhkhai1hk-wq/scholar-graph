"""Deterministic audit of live translation, source alignment and regression evidence."""
import hashlib
import json
import os
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))
from scholar_graph.api_repository import ApiRepository
from scholar_graph.translation import check_numbers, protect, used_terms
from scholar_graph.translation_routes import TranslationResponse
from scholar_graph.validation import ContractGate

BASELINE = '349369388b31033dc624ace815b9189a0569b4e4'


def git(*args):
    return subprocess.check_output(['git', *args], cwd=ROOT).decode('utf-8').strip()


def junit(name):
    suites = list(ET.parse(ROOT / 'tests/reports' / name).getroot().iter('testsuite'))
    return {k: sum(int(s.get(k, '0')) for s in suites)
            for k in ('tests', 'failures', 'errors', 'skipped')} | {
                'seconds': round(sum(float(s.get('time','0')) for s in suites), 6)}


def main():
    live = json.loads((ROOT / 'tests/reports/translation-live-results.json').read_text(encoding='utf-8'))
    run = live['runs'][-1]
    checks = {'last_live_run_passed': run['status'] == 'passed',
              'three_live_scopes': [c['request']['scope'] for c in run['cases']] == ['abstract','section','full']}
    repository = ApiRepository(ROOT / 'data/real-model/records', ContractGate())
    bundle = repository.paper(live['paper_id'])
    with (ROOT / 'pdf/1706.03762v7.pdf').open('rb') as file:
        checks['official_pdf_hash_matches'] = hashlib.file_digest(file, 'sha256').hexdigest() == live['pdf_sha256'] == bundle['paper_meta']['file_hash']
    originals = {c['chunk_id']: c for c in bundle['chunks']}
    checks['live_implementation_hash_matches'] = all(
        hashlib.sha256((ROOT / p).read_bytes().replace(b'\r\n', b'\n')).hexdigest() == digest
        for p, digest in run['implementation_sha256'].items())
    for case in run['cases']:
        scope = case['request']['scope']
        checks[scope + '_http_200_and_passed'] = case['http_status'] == 200 and case['status']=='passed' and all(case['checks'].values())
        path = ROOT / f'data/translation-acceptance/{scope}-response.json'
        value = json.loads(path.read_text(encoding='utf-8'))
        TranslationResponse.model_validate(value)
        manifest, numeric_valid, preserved, exact_sources = [], True, True, True
        for segment in value['segments']:
            source = originals.get(segment['source_chunk_id'])
            exact_sources &= bool(source) and segment['source_text'] == source['text'] and all(
                segment[k] == source[k] for k in ('paper_id','page_number','section_path','type'))
            try:
                check_numbers(segment['source_text'], segment['translated_text'], segment['source_chunk_id'])
            except Exception:
                numeric_valid = False
            masked, protected = protect(segment['source_text'], formula=segment['type']=='formula', numbers=False)
            preserved &= all(p in segment['translated_text'] for p in protected.values())
            if segment['type']=='formula':
                preserved &= segment['source_text'] == segment['translated_text']
            preserved &= re.findall(r'<[^>\n]+>', segment['source_text']) == re.findall(r'<[^>\n]+>', segment['translated_text'])
            manifest.append({'source_chunk_id': segment['source_chunk_id'], 'page_number': segment['page_number'],
                'source_sha256': hashlib.sha256(segment['source_text'].encode()).hexdigest(),
                'translation_sha256': hashlib.sha256(segment['translated_text'].encode()).hexdigest()})
        checks[scope+'_manifest_matches_local_response'] = manifest == case['manifest']
        checks[scope+'_exact_stored_anchors'] = exact_sources
        checks[scope+'_code_formula_structure_preserved'] = preserved
        checks[scope+'_numbers_source_backed'] = numeric_valid
        checks[scope+'_model_metadata_safe'] = all(set(call) == {
            'provider','model','phase','elapsed_seconds','prompt_tokens','completion_tokens',
            'total_tokens','http_status','status'} and call['provider']=='deepseek' and call['status']=='succeeded'
            for call in value['metadata']['model_calls'])
    full = json.loads((ROOT / 'data/translation-acceptance/full-response.json').read_text(encoding='utf-8'))
    checks['full_all_175_chunks'] = [s['source_chunk_id'] for s in full['segments']] == [c['chunk_id'] for c in bundle['chunks']] and len(full['segments']) == 175
    checks['full_all_markdown_anchors_once'] = all(full['markdown'].count(f'<a id="{c["chunk_id"]}"></a>') == 1 for c in bundle['chunks'])
    regression, no_key = junit('translation-pytest.xml'), junit('translation-no-key-pytest.xml')
    checks['full_regression_all_passed'] = regression['tests'] >= 384 and not any(regression[k] for k in ('failures','errors','skipped'))
    checks['no_key_live_skipped_only'] = no_key == {'tests':42,'failures':0,'errors':0,'skipped':1,'seconds':no_key['seconds']}
    files = sorted(set(git('diff', BASELINE, '--name-only').splitlines() + git('ls-files','--others','--exclude-standard').splitlines()))
    checks['only_backend_and_tests_changed'] = all(p.startswith(('backend/','tests/')) for p in files)
    checks['frontend_contracts_docs_unchanged'] = not git('diff', BASELINE, '--name-only', '--', 'frontend','contracts','docs','prompts','experiments','test-records')
    checks['pdf_directory_ignored'] = bool(git('check-ignore','pdf/1706.03762v7.pdf'))
    checks['no_pdf_tracked'] = not git('ls-files','--','pdf','*.pdf')
    key = os.environ.get('DEEPSEEK_API_KEY')
    checks['key_absent_from_all_task_files'] = not key or all(key.encode() not in (ROOT / p).read_bytes() for p in files if (ROOT / p).is_file())
    output = {'status': 'passed' if all(checks.values()) else 'failed', 'checks': checks,
              'check_count': len(checks), 'baseline': BASELINE, 'regression': regression, 'no_key': no_key,
              'live_counts': {c['request']['scope']:c.get('segments') for c in run['cases']},
              'implementation_sha256': {p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in (
                  'backend/scholar_graph/translation.py','backend/scholar_graph/translation_routes.py','backend/scholar_graph/deepseek_client.py')}}
    raw = json.dumps(output, ensure_ascii=False, indent=2) + '\n'
    if key and key in raw:
        raise RuntimeError('Credential safety check rejected audit')
    (ROOT / 'tests/reports/translation-audit.json').write_text(raw, encoding='utf-8')
    print(json.dumps({'status':output['status'],'checks':len(checks),'failed_checks':[k for k,v in checks.items() if not v],
                      'regression':regression,'no_key':no_key}, ensure_ascii=False))
    return 0 if output['status']=='passed' else 1


if __name__ == '__main__':
    raise SystemExit(main())

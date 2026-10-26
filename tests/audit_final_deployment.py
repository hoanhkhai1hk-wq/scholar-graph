"""Final cross-environment evidence audit; skipped tests never become passed tests."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
BASELINE = '8de7a907c212b49588fdf00ef9842e45863b273f'


def read(name):
    return json.loads((ROOT/'tests/reports'/name).read_text(encoding='utf-8'))


def junit(name):
    tree = ET.parse(ROOT/'tests/reports'/name).getroot()
    suites = list(tree.iter('testsuite'))
    stats = {k:sum(int(s.get(k,0)) for s in suites) for k in ('tests','failures','errors','skipped')}
    stats['passed'] = stats['tests']-stats['failures']-stats['errors']-stats['skipped']
    stats['skipped_cases'] = [{'name':c.get('name'),'reason':c.find('skipped').get('message')}
        for c in tree.iter('testcase') if c.find('skipped') is not None]
    return stats


def main():
    build = read('final-deployment-build.json')
    host = read('final-deployment-host-final.json')
    container = read('final-deployment-container.json')
    runtime = read('final-deployment-runtime.json')
    checks = {}
    checks['clean_remote_main_clone'] = build['clone']['clean'] and all(build['clone']['host_artifacts_absent'].values())
    checks['clone_unchanged_after_build_and_cases'] = build['clone']['clean_after_build_and_run']
    stage = next(s for s in build['steps'] if s['stage']=='build-no-cache')
    checks['actual_no_cache_build'] = stage['exit_code']==0 and '--no-cache' in stage['argv']
    checks['build_log_identity'] = hashlib.sha256(Path(stage['log']).read_bytes()).hexdigest()==stage['log_sha256']
    checks['image_sources_match_clean_clone'] = build['source_matches_clean_clone']
    checks['two_healthy_services_and_ports'] = all(s['healthy'] for s in runtime['services']) and set(runtime['http_status'].values())=={200}
    checks['both_image_revision_labels_match_clone'] = all(s['revision']==build['clone']['commit'] for s in runtime['services'])
    checks['runtime_public_model_full_checksum_verified'] = runtime['model_snapshot']['matches_fixed_revision_weights'] and runtime['model_snapshot']['bytes']==2271145830
    checks['resolved_vector_interpreter_keeps_venv'] = runtime['vector_runtime']['isolated_after_resolution']
    checks['ocr_preparation_and_final_test_sources_match_clone']=all(
        hashlib.sha256((Path(build['clone']['path'])/name).read_bytes()).hexdigest()==digest
        for name,digest in runtime['supplementary_source_sha256'].items())
    checks['no_official_corpus_or_credentials_in_images'] = all(s['input_audit']['passed'] for s in runtime['services'])
    checks['automatic_daily_configuration_active'] = runtime['scheduler']['scheduler_details']['enabled'] and runtime['scheduler']['scheduler_details']['interval_seconds']==86400 and runtime['scheduler']['scheduler_details']['active']
    stats = {'host_final':junit('final-deployment-host-final-pytest.xml'),
             'host_initial':junit('final-deployment-host-pytest.xml'),
             'container_initial':junit('final-deployment-container-before-runtime-fix-pytest.xml'),
             'container':junit('final-deployment-container-pytest.xml')}
    checks['first_container_three_failures_preserved'] = stats['container_initial']['failures']==3
    for name in ('host_final','container'):
        checks[name+'_full_layer_passed'] = stats[name]['tests']==613 and stats[name]['failures']==stats[name]['errors']==0
        checks[name+'_five_no_key_model_tests_skipped'] = sum('real model disabled' in (c['reason'] or '') for c in stats[name]['skipped_cases'])==5
    checks['container_no_key_qa_passed'] = container['no_key_qa']['http_status']==200 and not container['no_key_qa']['body']['refused'] and bool(container['no_key_qa']['body']['anchors'])
    for name, result in [('host',host),('container',container)]:
        checks[name+'_three_official_cases_passed'] = all(c['passed'] for c in result['cases'].values())
        for case in result['cases'].values():
            for row in case['uploads']:
                assert hashlib.sha256((ROOT/'pdf'/row['file']).read_bytes()).hexdigest()==row['sha256']
                assert row['initial_status_http']==404 and row['parse_status']['status']=='completed' and row['chunks']>0
    runs = container['automatic_public_runs']
    checks['two_real_timer_runs_have_public_queries'] = len(runs)>=2 and all(r.get('queries') for r in runs)
    timer_ids={e.get('run_id') for e in container['scheduler_events'] if e['event']=='run_finished'}
    checks['query_runs_match_automatic_timer_journal'] = all(r['run_id'] in timer_ids for r in runs)
    checks['timer_did_not_invent_successful_candidates'] = all(r['candidate_count']==len(r['candidates']) for r in runs)
    diff = subprocess.check_output(['git','diff',BASELINE,'--name-only','--','contracts','frontend','docs','prompts','experiments','test-records'],cwd=ROOT,text=True)
    checks['contracts_and_frontend_protected_paths_unchanged'] = not diff.strip()
    checks['pdf_ignored'] = subprocess.run(['git','check-ignore','pdf/1706.03762v7.pdf'],cwd=ROOT,capture_output=True).returncode==0
    key = os.environ.get('DEEPSEEK_API_KEY')
    artifacts = list((ROOT/'tests/reports').glob('final-deployment-*'))
    checks['key_absent_from_artifacts'] = all(not key or key.encode() not in p.read_bytes() for p in artifacts if p.is_file())
    result = {'passed':all(checks.values()),'checks':checks,'regression':stats,
              'image_source_commit':build['clone']['commit'],'initial_host_failure_preserved':stats['host_initial']['failures']>0}
    (ROOT/'tests/reports/final-deployment-audit.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False))
    return int(not result['passed'])


if __name__=='__main__':
    raise SystemExit(main())

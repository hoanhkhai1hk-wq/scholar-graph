"""Deterministically audit module-six samples, provenance, scopes and regression."""
import base64
import hashlib
import json
import os
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'backend'))
from scholar_graph.api_repository import ApiRepository
from scholar_graph.charts_3d import validate_3d
from scholar_graph.topology import parse_script
from scholar_graph.translation import check_numbers,protect
from scholar_graph.validation import ContractGate
from run_module6_completion_acceptance import CSV,BASELINE,prior_source


def digest(raw):return hashlib.sha256(raw).hexdigest()


def git(*args):return subprocess.check_output(['git',*args],cwd=ROOT).decode('utf-8').strip()


def read(name):return json.loads((ROOT/'tests/reports'/name).read_text(encoding='utf-8'))


def junit(name):
    suites=list(ET.parse(ROOT/'tests/reports'/name).getroot().iter('testsuite'))
    return {k:sum(int(s.get(k,'0')) for s in suites) for k in ('tests','failures','errors','skipped')} | {
        'seconds':round(sum(float(s.get('time','0')) for s in suites),6)}


def main():
    run=read('module6-completion-results.json')['runs'][-1]
    gate=ContractGate()
    repo=ApiRepository(ROOT/'data/real-model/records',gate)
    bundle=repo.paper(run['paper_id'])
    checks={'last_live_run_passed':run['status']=='passed',
        'all_four_cases_passed':[c['name'] for c in run['cases']]==['topology','chart_3d','back_translation_abstract','back_translation_full'] and
            all(c['status']=='passed' and c['http_status']==200 for c in run['cases']),
        'implementation_matches_live_run':all(digest((ROOT/p).read_bytes().replace(b'\r\n',b'\n'))==d for p,d in run['implementation_sha256'].items())}
    with (ROOT/'pdf/1706.03762v7.pdf').open('rb') as file:
        checks['official_pdf_matches_stored_records']=hashlib.file_digest(file,'sha256').hexdigest()==run['pdf_sha256']==bundle['paper_meta']['file_hash']
    topo=read('module6-topology.json')['response']
    external=read('module6-topology-external-validation.json')
    for script in topo['scripts']:
        kind=script['format'];extension={'dot':'dot','mermaid':'mmd','tikz':'tex'}[kind]
        source=(ROOT/f'tests/reports/module6-topology.{extension}').read_text(encoding='utf-8')
        nodes,edges=parse_script(source,kind)
        checks[kind+'_file_matches_endpoint']=source==script['script']
        checks[kind+'_parsed_16_nodes_20_edges']=len(nodes)==16 and len(edges)==20 and script['validation']['passed']
        if kind in external:
            checks[kind+'_independent_parser_and_source_hash']=external[kind]['status']=='passed' and external[kind]['source_sha256']==digest(source.encode())
    checks['tikz_not_misrepresented_as_compiled']=not next(s for s in topo['scripts'] if s['format']=='tikz')['validation']['compiler_executed']
    for item in topo['nodes']+topo['edges']:
        for anchor in item['anchors']:gate.anchor(anchor,[bundle])
    checks['all_topology_anchors_real']=True
    svg_path=ROOT/'tests/reports/module6-topology-dot.svg'
    svg=ET.parse(svg_path).getroot()
    checks['real_graphviz_svg_counts']=len([e for e in svg.iter() if e.get('class')=='node'])==16 and len([e for e in svg.iter() if e.get('class')=='edge'])==20
    checks['svg_hash_matches_external_render']=digest(svg_path.read_text(encoding='utf-8').encode())==external['dot']['svg_sha256']
    chart=json.loads((ROOT/'data/module6-completion/chart3d-response.json').read_text(encoding='utf-8'))
    validate_3d(chart,CSV,['Base','Big'],'epoch',gate)
    checks['3d_chart_frozen_record_data_trends_and_png_valid']=True
    checks['csv_artifact_is_exact_input']=(ROOT/'tests/reports/module6-trends.csv').read_bytes().replace(b'\r\n',b'\n')==CSV
    chart_case=next(c for c in run['cases'] if c['name']=='chart_3d')
    png=(ROOT/'tests/reports/module6-3d-bar.png').read_bytes()
    checks['png_endpoint_file_and_digest_match']=png==base64.b64decode(chart['chart']['image_ref'].split(',')[1]) and digest(png)==chart_case['png']['sha256']
    checks['model_caption_not_numeric_enumeration']=chart['metadata']['caption_method']=='deepseek_grounded_selection' and '上升' in chart['chart']['caption'] and '放缓' in chart['chart']['caption']
    checks['all_caption_rows_cited']=all(c['row_numbers']==[2,3,4,5] for c in chart['conclusions'])
    for scope in ('abstract','full'):
        prior,proof=prior_source(scope)
        previous={s['source_chunk_id']:s for s in prior['segments']}
        response=json.loads((ROOT/f'data/module6-completion/en-{scope}-response.json').read_text(encoding='utf-8'))
        case=next(c for c in run['cases'] if c['name']=='back_translation_'+scope)
        actual=[]
        preserved=True
        for segment in response['segments']:
            p=previous[segment['source_chunk_id']]
            preserved &= segment['source_text']==p['translated_text'] and all(segment[k]==p[k] for k in ('paper_id','page_number','section_path','type'))
            check_numbers(segment['source_text'],segment['translated_text'],segment['source_chunk_id'])
            _,spans=protect(segment['source_text'],formula=segment['type']=='formula',numbers=False)
            preserved &= all(value in segment['translated_text'] for value in spans.values())
            actual.append({'source_chunk_id':segment['source_chunk_id'],'source_sha256':digest(segment['source_text'].encode()),
                           'translation_sha256':digest(segment['translated_text'].encode())})
        checks[scope+'_uses_exact_task_four_chinese_manifest']=proof==case['chinese_input_proof']
        checks[scope+'_english_mapping_numbers_and_protection_valid']=preserved and actual==case['manifest']
        checks[scope+'_all_selected_chunks_returned']=len(response['segments'])==len(prior['segments'])==({'abstract':6,'full':175}[scope])
        checks[scope+'_target_and_input_chain_explicit']=response['target']=='en' and response['metadata']['source_input']=='client_prior_zh_response_validated_against_original_chunks'
        if scope=='full':checks['english_full_has_all_markdown_anchors']=all(response['markdown'].count(f'<a id="{s["source_chunk_id"]}"></a>')==1 for s in response['segments'])
    calls=[call for case in run['cases'] for call in case.get('metadata',{}).get('model_calls',[])]
    allowed={'provider','model','phase','elapsed_seconds','prompt_tokens','completion_tokens','total_tokens','http_status','status'}
    checks['only_safe_real_model_metadata']=bool(calls) and all(set(c)==allowed and c['status']=='succeeded' and c['http_status']==200 and c['provider']=='deepseek' for c in calls)
    full,no_key=junit('module6-completion-pytest.xml'),junit('module6-completion-no-key-pytest.xml')
    checks['full_regression_all_passed']=full['tests']>=448 and not any(full[k] for k in ('failures','errors','skipped'))
    checks['no_key_real_tests_skipped_not_failed']=no_key['tests']==64 and no_key['skipped']==2 and not no_key['failures'] and not no_key['errors']
    changed=sorted(set(git('diff',BASELINE,'--name-only').splitlines()+git('ls-files','--others','--exclude-standard').splitlines()))
    checks['only_backend_and_tests_changed']=all(p.startswith(('backend/','tests/')) for p in changed)
    checks['frontend_contracts_docs_unchanged']=not git('diff',BASELINE,'--name-only','--','frontend','contracts','docs','prompts','experiments','test-records')
    checks['old_reports_preserved']=all(p.startswith('tests/reports/module6') for p in git('diff',BASELINE,'--name-only','--','tests/reports').splitlines())
    checks['pdf_directory_ignored_untracked']=bool(git('check-ignore','pdf/1706.03762v7.pdf')) and not git('ls-files','--','pdf','*.pdf')
    key=os.environ.get('DEEPSEEK_API_KEY')
    checks['actual_key_not_in_task_files']=not key or all(key.encode() not in (ROOT/p).read_bytes() for p in changed if (ROOT/p).is_file())
    value={'status':'passed' if all(checks.values()) else 'failed','check_count':len(checks),'checks':checks,
           'baseline':BASELINE,'regression':full,'no_key':no_key}
    raw=json.dumps(value,ensure_ascii=False,indent=2)+'\n'
    if key and key in raw:raise RuntimeError('Credential check rejected audit')
    (ROOT/'tests/reports/module6-completion-audit.json').write_text(raw,encoding='utf-8')
    print(json.dumps({'status':value['status'],'checks':len(checks),'failed':[k for k,v in checks.items() if not v],
                      'regression':full,'no_key':no_key},ensure_ascii=False))
    return 0 if value['status']=='passed' else 1


if __name__=='__main__':raise SystemExit(main())

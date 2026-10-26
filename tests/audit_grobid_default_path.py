"""Audit actual published groups, unchanged contracts, and final real full regression."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from xml.etree import ElementTree as ET

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'backend'))
from scholar_graph.storage import RecordStore
from scholar_graph.validation import ContractGate
from scholar_graph.reference_identity import title_key

BASE='a7aacc3672bb8a58e3e723b0ce235ce3b9c19515'


def stats(name):
    tree=ET.parse(ROOT/'tests/reports'/name)
    suites=list(tree.iter('testsuite'))
    result={k:sum(int(s.get(k,0)) for s in suites) for k in ('tests','failures','errors','skipped')}
    result['passed']=result['tests']-result['failures']-result['errors']-result['skipped']
    result['skips']=[{'name':c.get('name'),'reason':c.find('skipped').get('message')} for c in tree.iter('testcase') if c.find('skipped') is not None]
    names={'test_real_local_bge_m3_dense_sparse_chroma','test_official_541_page_longbook_full_layer',
        'test_http_real_paddleocr_fallback','test_actual_paddleocr_scanned_pdf'}
    cases=[c for c in tree.iter('testcase') if c.get('name') in names]
    result['live_cases_passed']=len(cases)==len(names) and all(c.find('failure') is None and c.find('skipped') is None for c in cases)
    return result


def main():
    reports=ROOT/'tests/reports'
    data=json.loads((reports/'grobid-default-path-live.json').read_text(encoding='utf-8'))
    checks={'live_probe_passed':data['passed']}
    pid='paper-'+data['sha256']
    bundles={}
    for group,row in data['groups'].items():
        store=RecordStore(Path(data['run_root'])/group,ContractGate())
        bundles[group]=store.load(store.root/'papers'/pid)
        checks[group+'_all_endpoint_checks']=all(row['checks'].values())
        checks[group+'_counts_match_disk']=all(len(bundles[group][key])==n for key,n in row['counts'].items())
        checks[group+'_saved_method_matches_response']=row['parse_metadata']['method']==row['full_parse_metadata']['method']
    enabled=data['groups']['enabled'];fallback=data['groups']['unreachable']
    checks['methods_are_explicit']=enabled['parse_metadata']['method']=='mineru+grobid' and fallback['parse_metadata']['method']=='mineru-fallback'
    checks['unreachable_has_real_reason']=fallback['parse_metadata']['grobid_error']['details']['failure_kind']=='unavailable'
    checks['mineru_chunks_and_anchors_unchanged']=bundles['enabled']['chunks']==bundles['unreachable']['chunks']
    checks['reference_identity_and_ordinals_preserved']=[(r['ref_id'],r['paper_id'],r['number']) for r in bundles['enabled']['reference_entries']]==[(r['ref_id'],r['paper_id'],r['number']) for r in bundles['unreachable']['reference_entries']]
    checks['source_pdf_hash_matches']=hashlib.sha256((ROOT/'pdf'/data['file']).read_bytes()).hexdigest()==data['sha256']
    checks['core_sources_match_live_run']=all(hashlib.sha256((ROOT/'backend/scholar_graph'/name).read_bytes()).hexdigest()==digest for name,digest in data['source_sha256'].items())
    first=' '.join(c['text'] for c in bundles['enabled']['chunks'] if c['page_number']==1)
    checks['authors_have_original_page_text']=all(title_key(a) in title_key(first) for a in enabled['paper_meta']['authors'])
    checks['known_org_false_authors_removed']=not {'Google Brain','Google Research'} & set(enabled['paper_meta']['authors'])
    checks['unverified_version_date_not_published']=enabled['paper_meta']['year']==fallback['paper_meta']['year'] and 'year' in enabled['full_parse_metadata']['withheld_header_fields']
    final=stats('grobid-default-path-pytest.xml');initial=stats('grobid-default-path-initial-pytest.xml')
    checks['full_regression_passed']=final['tests']==628 and final['failures']==final['errors']==0 and final['skipped']==5
    checks['five_no_key_skips_preserved']=len(final['skips'])==5 and all('real model disabled' in s['reason'] for s in final['skips'])
    checks['real_vector_ocr_and_longbook_ran']=final['live_cases_passed']
    checks['initial_failure_evidence_preserved']=initial['failures']==2
    checks['protected_paths_unchanged']=not subprocess.check_output(['git','diff',BASE,'--name-only','--','contracts','frontend','docs','prompts','experiments','test-records'],cwd=ROOT).strip()
    checks['official_corpus_ignored']=subprocess.run(['git','check-ignore','pdf/1706.03762v7.pdf'],cwd=ROOT,capture_output=True).returncode==0
    checks['official_corpus_not_tracked']=not subprocess.check_output(['git','ls-files','--','pdf'],cwd=ROOT).strip()
    key=os.environ.get('DEEPSEEK_API_KEY')
    files=[p for p in reports.glob('grobid-default-path*') if p.is_file()]
    tracked=[ROOT/p for p in subprocess.check_output(['git','ls-files','-z'],cwd=ROOT).decode('utf-8').split('\0') if p]
    checks['known_key_absent_from_sources_and_evidence']=all(not key or key.encode() not in p.read_bytes() for p in files+tracked if p.is_file())
    image=subprocess.check_output(['docker','inspect','scholar-graph-grobid-grobid-1','--format','{{.Config.Image}}'],text=True).strip()
    checks['actual_grobid_image']=image=='grobid/grobid:0.9.1-crf'
    result={'passed':all(checks.values()),'checks':checks,'regression':final,'initial_regression':initial,
        'baseline':BASE,'service_image':image,'live_revision':data['source_revision'],'opaque_key_scan_available':bool(key)}
    (reports/'grobid-default-path-audit.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'passed':result['passed'],'checks':checks},ensure_ascii=False))
    return int(not result['passed'])


if __name__=='__main__':raise SystemExit(main())

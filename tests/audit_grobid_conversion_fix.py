"""Revalidate actual publications, source TEI, frozen contracts and default wiring."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))
from scholar_graph.api import create_app
from scholar_graph.grobid import GrobidClient, NS, authors
from scholar_graph.storage import RecordStore
from scholar_graph.validation import ContractGate
from run_grobid_acceptance import bundle_summary
from run_grobid_conversion_fix import normalization_evidence

BASELINE = 'a3725bfed43fedf13be9fb7597749e72f9a7a9f7'


def main():
    report = json.loads((ROOT / 'tests/reports/grobid-conversion-fix-live.json').read_text(encoding='utf-8'))
    checks = {}
    folder, gate = ROOT / report['local_artifacts'], ContractGate()
    source = ROOT / 'pdf/1706.03762v7.pdf'
    checks['official_pdf_identity'] = hashlib.sha256(source.read_bytes()).hexdigest() == report['input']['sha256']
    payload = (folder / 'grobid-response.tei.xml').read_bytes()
    checks['actual_tei_identity'] = hashlib.sha256(payload).hexdigest() == report['service_call']['tei_sha256']
    tree = ET.fromstring(payload)
    pid = 'paper-' + report['input']['sha256']
    bundles = []
    for name, key in (('mineru-only', 'mineru'), ('with-grobid', 'output')):
        store = RecordStore(folder / name, gate)
        bundle = store.load(store.root / 'papers' / pid)
        gate.bundle(bundle)
        measured = bundle_summary(bundle)
        checks[name + '_schemas_foreign_keys_and_saved_counts'] = all(measured[x] == report[key][x]
            for x in ('paper_meta', 'counts', 'reference_coverage', 'samples'))
        bundles.append(bundle)
    before, after = bundles
    converted = GrobidClient('http://127.0.0.1:8070')._convert(before, tree)
    gate.bundle(converted)
    checks['tei_conversion_matches_entire_publication'] = converted == after
    checks['chunks_retained'] = before['chunks'] == after['chunks']
    checks['null_and_name_counts_recomputed'] = normalization_evidence(tree, after) == report['normalization']
    checks['reference_one_title_venue_are_null'] = after['reference_entries'][0]['title'] is None and after['reference_entries'][0]['venue'] is None
    checks['reference_one_actual_names_have_spacing'] = after['reference_entries'][0]['authors'] == ['Jimmy Lei Ba', 'Jamie Ryan Kiros', 'Geoffrey E Hinton']
    checks['header_names_match_real_tei_components'] = authors(tree.find('t:teiHeader', NS)) == after['paper_meta']['authors']
    groups = list((folder / 'with-grobid/papers').glob('paper-*'))
    checks['completed_one_real_paper_group'] = len(groups) == report['published_groups'] == 1 and report['status']['status'] == 'completed'
    diff = subprocess.check_output(['git', 'diff', BASELINE, '--name-only', '--', 'contracts', 'frontend', 'docs', 'prompts', 'experiments', 'test-records'], cwd=ROOT, text=True)
    checks['contracts_and_protected_paths_unchanged'] = not diff.strip()
    ignored = subprocess.run(['git', 'check-ignore', 'pdf/1706.03762v7.pdf'], cwd=ROOT, capture_output=True)
    checks['pdf_ignored'] = ignored.returncode == 0
    # Runtime factory inspection, including a configured URL: explicit CLI only.
    for key, value in [('GROBID_URL', 'http://127.0.0.1:8070'), ('SCHOLAR_GRAPH_DEDUP_MODE', 'off'),
                       ('SCHOLAR_GRAPH_RETRIEVAL_MODE', 'lexical'), ('SCHOLAR_GRAPH_QA_MODE', 'extractive')]:
        os.environ[key] = value
    app = create_app(data_dir=folder / 'default-factory-inspection')
    checks['default_http_upload_not_enabled'] = app.state.uploads.factory().grobid is None
    checks['default_arxiv_not_enabled'] = app.state.arxiv_fetcher._pipeline(after['paper_meta']).grobid is None
    suites = ET.parse(ROOT / 'tests/reports/grobid-conversion-fix-pytest.xml').getroot().findall('testsuite')
    regression = {key: sum(int(x.get(key, 0)) for x in suites) for key in ('tests', 'failures', 'errors', 'skipped')}
    checks['full_regression_passes'] = regression['tests'] >= 564 and regression['failures'] == regression['errors'] == 0
    key = os.environ.get('DEEPSEEK_API_KEY')
    artifacts = [ROOT / 'tests/reports/grobid-conversion-fix-live.json', ROOT / 'tests/reports/grobid-conversion-fix-acceptance.md',
                 ROOT / 'tests/reports/grobid-conversion-fix-pytest.xml']
    checks['credential_absent'] = all(not key or key.encode() not in path.read_bytes() for path in artifacts)
    result = {'checks': checks, 'regression': regression, 'passed': all(checks.values()),
              'contracts_baseline': BASELINE, 'default_http_grobid': False, 'default_arxiv_grobid': False}
    (ROOT / 'tests/reports/grobid-conversion-fix-audit.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())

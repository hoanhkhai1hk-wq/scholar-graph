"""Recheck official file identity, stored graph joins, proof sidecars and regression."""
from collections import Counter
import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))
from scholar_graph.api_repository import ApiRepository
from scholar_graph.graph_service import build_graph
from scholar_graph.reference_identity import title_key
from scholar_graph.normalize import citation_links
from scholar_graph.validation import ContractGate

BASELINE = 'e3df9a97865b748c5ac174c18a5690097014a40a'


def main():
    report = json.loads((ROOT / 'tests/reports/graph-identity-live.json').read_text(encoding='utf-8'))
    repository = ApiRepository(ROOT / report['local_artifacts'], ContractGate())
    checks = {}
    bundles = [repository.paper(item['paper_id']) for item in report['inputs']]
    for item, bundle in zip(report['inputs'], bundles):
        source = ROOT / 'pdf' / item['filename']
        checks[item['label'] + '_official_file_and_saved_counts'] = (
            hashlib.sha256(source.read_bytes()).hexdigest() == item['sha256'] == bundle['paper_meta']['file_hash']
            and item['page_count'] == bundle['paper_meta']['page_count']
            and all(len(bundle[key]) == item[field] for key, field in [('chunks', 'chunks'),
                ('reference_entries', 'references'), ('citation_links', 'citation_links')]))
        repository.gate.bundle(bundle)
    graph = build_graph(bundles, repository.gate)
    checks['published_graph_equals_http_evidence'] = graph == report['graph']
    checks['saved_local_response_equals_evidence'] = graph == json.loads((repository.root / 'graph-response.json').read_text(encoding='utf-8'))
    by_paper = {b['paper_meta']['id']: b for b in bundles}
    resolutions = graph['diagnostics']['reference_resolutions']
    expected = {(b['paper_meta']['id'], r['ref_id']) for b in bundles for r in b['reference_entries']}
    checks['every_reference_has_one_resolution'] = len(resolutions) == len(expected) and {
        (r['paper_id'], r['ref_id']) for r in resolutions} == expected
    for resolution in resolutions:
        for quote in resolution['bibliography']:
            repository.gate.anchor(quote['anchor'], bundles, quote=quote['quote'])
        assert resolution['method'] in ('arxiv', 'doi', 'title', 'author-year', None)
        assert (resolution['target_paper_id'] is None) == (resolution['status'] == 'unresolved')
        assert resolution['attempted_methods']
        if resolution['status'] == 'resolved':
            assert resolution['method'] and resolution['evidence']
    checks['all_resolution_methods_and_bibliography_anchors_valid'] = True
    proofs = graph['diagnostics']['edge_evidence']
    checks['one_proof_per_graph_edge'] = len(proofs) == len(graph['edges']) and sorted(
        p['edge_index'] for p in proofs) == list(range(len(graph['edges'])))
    for proof in proofs:
        edge = graph['edges'][proof['edge_index']]
        repository.gate.record('GraphEdge', edge)
        assert edge['anchor'] == proof['anchor']
        assert (edge['from_paper_id'], edge['to_paper_id']) == (proof['from_paper_id'], proof['to_paper_id'])
        if edge['status'] != 'verified':
            continue
        repository.gate.anchor(edge['anchor'], bundles)
        source = by_paper[edge['from_paper_id']]
        chunk = next(c for c in source['chunks'] if c['chunk_id'] == edge['anchor']['chunk_id'])
        assert chunk['text'] == proof['body_quote']
        for reference in proof['references']:
            assert any(link['ref_id'] == reference['ref_id'] and link['chunk_id'] == chunk['chunk_id']
                       and link['citation_number'] == reference['reference_number'] for link in source['citation_links'])
            assert any(link['ref_id'] == reference['ref_id'] for link in citation_links([chunk], source['reference_entries']))
            assert reference['target_paper_id'] == edge['to_paper_id']
            if reference['method'] == 'title':
                evidence = reference['evidence'][0]
                title = evidence['target_title']
                assert title_key(title['text']) == title_key(reference['identity']['title'])
                if title['anchor']:
                    repository.gate.anchor(title['anchor'], bundles, quote=title['text'])
    checks['all_verified_edges_join_real_citationlink_reference_chunk_and_target'] = True
    counts = report['counts']
    checks['unresolved_totals_are_honest'] = (counts['references'] == len(expected)
        and counts['unresolved_references'] == sum(r['status'] == 'unresolved' for r in resolutions)
        and counts['resolved_references'] + counts['unresolved_references'] == counts['references'])
    checks['all_unresolved_reasons_preserved'] = dict(Counter(r['reason'] for r in resolutions
        if r['status'] == 'unresolved')) == report['unresolved_reasons']
    labels = report['labels']
    pairs = {(labels[e['from_paper_id']], labels[e['to_paper_id']]) for e in graph['edges'] if e['status'] == 'verified'}
    checks['three_requested_pairs_verified'] = {('BERT', 'Attention'), ('GPT-1', 'Attention'),
        ('FlashAttention', 'Attention')} <= pairs
    # Execute only our repository's frozen baseline functions on the same
    # freshly parsed chunks; do not edit or republish the baseline projection.
    previous = {}
    for module in ('normalize', 'citation_graph'):
        namespace = {'__package__': 'scholar_graph'}
        code = subprocess.check_output(['git', 'show', BASELINE + ':backend/scholar_graph/' + module + '.py'], cwd=ROOT)
        exec(code.decode('utf-8'), namespace)
        previous[module] = namespace
    projected = copy.deepcopy(bundles)
    for bundle in projected:
        bundle['reference_entries'] = previous['normalize']['reference_entries'](bundle['chunks'], bundle['paper_meta']['id'])
        bundle['citation_links'] = previous['normalize']['citation_links'](bundle['chunks'], bundle['reference_entries'])
    before_edges, before_unresolved = previous['citation_graph']['citation_edges'](projected, repository.gate)
    baseline_projection = {'nodes': len(projected), 'references': sum(len(b['reference_entries']) for b in projected),
        'edges': len(before_edges), 'unresolved_reasons': dict(Counter(r['reason'] for r in before_unresolved))}
    checks['same_chunks_baseline_projection_measured'] = len(projected) == len(bundles)
    diff = subprocess.check_output(['git', 'diff', BASELINE, '--name-only', '--',
        'contracts', 'frontend', 'docs', 'prompts', 'experiments', 'test-records'], cwd=ROOT, text=True)
    checks['contracts_and_protected_paths_unchanged'] = not diff.strip()
    checks['official_pdf_ignored'] = all(subprocess.run(['git', 'check-ignore', 'pdf/' + i['filename']],
        cwd=ROOT, capture_output=True).returncode == 0 for i in report['inputs'])
    suites = ET.parse(ROOT / 'tests/reports/graph-identity-pytest.xml').getroot().findall('testsuite')
    regression = {key: sum(int(s.get(key, 0)) for s in suites) for key in ('tests', 'failures', 'errors', 'skipped')}
    checks['full_regression_without_failures'] = regression['tests'] >= 564 and regression['failures'] == regression['errors'] == 0
    checks['new_regression_cases_executed'] = sum(1 for s in suites for c in s.findall('testcase')
        if ('test_reference_identity' in c.get('classname', '') or 'test_graph_identity_evidence' in c.get('classname', ''))
        and c.find('skipped') is None) >= 30
    secret = os.environ.get('DEEPSEEK_API_KEY')
    artifacts = [ROOT / ('tests/reports/graph-identity-' + suffix) for suffix in
                 ('live.json', 'acceptance.md', 'pytest.xml')]
    checks['credential_absent_from_artifacts'] = all(not secret or secret.encode() not in p.read_bytes() for p in artifacts)
    result = {'checks': checks, 'passed': all(checks.values()), 'regression': regression,
              'baseline': BASELINE, 'verified_pairs': sorted(pairs), 'counts': counts,
              'same_chunks_baseline_projection': baseline_projection}
    (ROOT / 'tests/reports/graph-identity-audit.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())

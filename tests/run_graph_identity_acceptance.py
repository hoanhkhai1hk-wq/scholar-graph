"""Reparse four official pdf/ files into an empty store and query the real graph route."""
from collections import Counter
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from uuid import uuid4

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))
from scholar_graph.api import create_app
from scholar_graph.pipeline import Pipeline
from scholar_graph.validation import ContractGate

SOURCES = [('Attention', '1706.03762v7.pdf'), ('BERT', 'N19-1423.pdf'),
           ('GPT-1', 'language_understanding_paper.pdf'), ('FlashAttention', '2205.14135v2.pdf')]


def main():
    for name, value in [('SCHOLAR_GRAPH_DEDUP_MODE', 'off'), ('SCHOLAR_GRAPH_RETRIEVAL_MODE', 'lexical'),
                        ('SCHOLAR_GRAPH_QA_MODE', 'extractive')]:
        os.environ[name] = value
    folder = ROOT / 'data/graph-identity' / uuid4().hex
    gate, parsed, labels, inputs = ContractGate(), [], {}, []
    assert not folder.exists()
    report = {'scope': '官方 pdf/ 真文件；MinerU 本地直跑；不调用模型 API、不需要 Key',
        'started_utc': datetime.now(timezone.utc).isoformat(),
        'baseline': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
        'local_artifacts': str(folder.relative_to(ROOT)), 'fresh_store': True,
        'versions': {name: importlib.metadata.version(name) for name in ('mineru', 'pypdf', 'fastapi')},
        'passed': False, 'inputs': inputs}
    path = ROOT / 'tests/reports/graph-identity-live.json'

    def save():
        value = json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + '\n'
        secret = os.environ.get('DEEPSEEK_API_KEY')
        if secret and secret in value:
            raise RuntimeError('credential detected; evidence not saved')
        path.write_text(value, encoding='utf-8')

    save()
    try:
        for label, filename in SOURCES:
            source = ROOT / 'pdf' / filename
            start = time.perf_counter()
            pipeline = Pipeline(folder)
            bundle = pipeline.parse(source)
            gate.bundle(bundle)
            assert pipeline.store.load(pipeline.last_output) == bundle
            parsed.append(bundle)
            pid = bundle['paper_meta']['id']
            labels[pid] = label
            refs = bundle['reference_entries']
            inputs.append({'label': label, 'filename': filename, 'bytes': source.stat().st_size,
                'sha256': hashlib.sha256(source.read_bytes()).hexdigest(), 'paper_id': pid,
                'page_count': bundle['paper_meta']['page_count'], 'elapsed_seconds': round(time.perf_counter() - start, 6),
                'chunks': len(bundle['chunks']), 'references': len(refs), 'citation_links': len(bundle['citation_links']),
                'reference_coverage': {key: sum(bool(r[key]) for r in refs) for key in ('title', 'authors', 'year', 'doi', 'arxiv_id')},
                'status': pipeline.last_job.current, 'schema_and_anchor_validation': 'passed'})
            print(json.dumps(inputs[-1], ensure_ascii=False), flush=True)
            save()
        app = create_app(data_dir=folder)
        start = time.perf_counter()
        response = TestClient(app).get('/api/v1/graph', params=[('paper_ids', b['paper_meta']['id']) for b in parsed])
        response.raise_for_status()
        graph = response.json()
        (folder / 'graph-response.json').write_text(json.dumps(graph, ensure_ascii=False, indent=2), encoding='utf-8')
        pairs = sorted({(labels[e['from_paper_id']], labels[e['to_paper_id']]) for e in graph['edges'] if e['status'] == 'verified'})
        expected = [('BERT', 'Attention'), ('GPT-1', 'Attention'), ('FlashAttention', 'Attention')]
        missing = [pair for pair in expected if pair not in pairs]
        report.update(graph_http_status=response.status_code, graph_elapsed_seconds=round(time.perf_counter() - start, 6),
            labels=labels, graph=graph, verified_pairs=pairs, missing_expected_pairs=missing,
            counts={'nodes': len(graph['nodes']), 'edges': len(graph['edges']),
                'verified_edges': sum(e['status'] == 'verified' for e in graph['edges']),
                'verified_pairs': len(pairs), 'references': graph['diagnostics']['reference_count'],
                'resolved_references': graph['diagnostics']['resolved_reference_count'],
                'unresolved_references': graph['diagnostics']['unresolved_reference_count']},
            unresolved_reasons=dict(Counter(r['reason'] for r in graph['diagnostics']['reference_resolutions'] if r['status'] == 'unresolved')),
            method_counts=dict(Counter(r['method'] for r in graph['diagnostics']['reference_resolutions'] if r['status'] == 'resolved')))
        report['passed'] = not missing and report['counts']['verified_pairs'] >= 3
    except Exception as error:
        report['error'] = {'type': type(error).__name__, 'message': str(error)[:1500]}
    report['finished_utc'] = datetime.now(timezone.utc).isoformat()
    save()
    print(json.dumps({k: report.get(k) for k in ('passed', 'counts', 'verified_pairs', 'unresolved_reasons', 'method_counts', 'error')}, ensure_ascii=False))
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())

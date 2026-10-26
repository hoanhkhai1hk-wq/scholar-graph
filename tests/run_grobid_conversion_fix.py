"""Real 0.9.1-crf full-document publication, preserving old acceptance reports."""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from uuid import uuid4

import httpx
from defusedxml import ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from scholar_graph.grobid import GrobidClient, NS, person_name
from scholar_graph.pipeline import Pipeline
from scholar_graph.validation import ContractGate
from run_grobid_acceptance import bundle_summary, command


class CaptureTransport(httpx.HTTPTransport):
    """Pass through the actual client's network request; do not substitute TEI."""
    def handle_request(self, request):
        started = time.perf_counter()
        response = super().handle_request(request)
        response.read()
        self.elapsed_seconds = time.perf_counter() - started
        self.status_code = response.status_code
        self.request_path = request.url.path
        self.payload = response.content
        return response


def old_text(node):
    return " ".join("".join(node.itertext()).split()) if node is not None else None


def normalization_evidence(root, bundle):
    changed, title_count, venue_count = [], 0, 0
    for index, item in enumerate(root.findall('.//t:listBibl/t:biblStruct', NS)):
        ref = bundle['reference_entries'][index]
        before = {'title': old_text(item.find('t:analytic/t:title', NS)) or old_text(item.find('t:monogr/t:title', NS)),
                  'venue': old_text(item.find('t:monogr/t:title', NS))}
        fields = [key for key in ('title', 'venue') if before[key] == '' and ref[key] is None]
        title_count += 'title' in fields
        venue_count += 'venue' in fields
        if fields:
            changed.append({'number': ref['number'], 'fields': fields,
                            'before': {key: before[key] for key in fields}, 'after': {key: ref[key] for key in fields}})
    names = []
    for author in root.findall('.//t:author', NS):
        person = author.find('t:persName', NS)
        if person is not None:
            fixed = person_name(person)
            if fixed:
                names.append({'before': old_text(person), 'after': fixed})
    changed_names = [value for value in names if value['before'] != value['after']]
    return {'title_empty_to_null': title_count, 'venue_empty_to_null': venue_count,
            'affected_reference_entries': len(changed), 'changes': changed,
            'person_names_checked': len(names), 'person_names_changed': len(changed_names),
            'person_name_samples': changed_names[:14]}


def save(report):
    raw = json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + '\n'
    key = os.environ.get('DEEPSEEK_API_KEY')
    if key and key in raw:
        raise RuntimeError('credential in evidence; not saved')
    (ROOT / 'tests/reports/grobid-conversion-fix-live.json').write_text(raw, encoding='utf-8')


def main():
    for key, value in [('SCHOLAR_GRAPH_DEDUP_MODE', 'off'), ('SCHOLAR_GRAPH_QA_MODE', 'extractive'),
                       ('SCHOLAR_GRAPH_RETRIEVAL_MODE', 'lexical')]:
        os.environ[key] = value
    source = ROOT / 'pdf/1706.03762v7.pdf'
    raw = source.read_bytes()
    folder = ROOT / 'data/grobid-conversion-fix' / uuid4().hex
    gate = ContractGate()
    report = {'scope': '官方 pdf/ 真文件；真实 GROBID 0.9.1-crf + MinerU；无模型API/Key',
        'timestamp_utc': datetime.now(timezone.utc).isoformat(),
        'revision': command('git', 'rev-parse', 'HEAD')['stdout'], 'local_artifacts': str(folder.relative_to(ROOT)),
        'input': {'filename': source.name, 'sha256': hashlib.sha256(raw).hexdigest(), 'bytes': len(raw)},
        'published_groups': 0, 'passed': False}
    save(report)
    try:
        with httpx.Client(trust_env=False, timeout=15) as health:
            checks = {}
            for endpoint in ('isalive', 'version'):
                response = health.get('http://127.0.0.1:8070/api/' + endpoint)
                response.raise_for_status()
                checks[endpoint] = {'status': response.status_code, 'body': response.text}
            report['service'] = checks
        baseline = Pipeline(folder / 'mineru-only')
        started = time.perf_counter()
        before = baseline.parse(source)
        report['mineru'] = {'elapsed_seconds': round(time.perf_counter()-started, 6), **bundle_summary(before)}
        transport = CaptureTransport()
        client = GrobidClient('http://127.0.0.1:8070', timeout=300, transport=transport)
        enriched = Pipeline(folder / 'with-grobid', grobid=client)
        started = time.perf_counter()
        bundle = enriched.parse(source)
        gate.bundle(bundle)
        loaded = enriched.store.load(enriched.last_output)
        (folder / 'grobid-response.tei.xml').write_bytes(transport.payload)
        tree = ET.fromstring(transport.payload)
        report.update(published_groups=len(list((enriched.store.root / 'papers').glob('paper-*'))),
            elapsed_seconds=round(time.perf_counter()-started, 6),
            service_call={'status': transport.status_code, 'path': transport.request_path,
                          'elapsed_seconds': round(transport.elapsed_seconds, 6),
                          'tei_sha256': hashlib.sha256(transport.payload).hexdigest(), 'tei_bytes': len(transport.payload)},
            status=enriched.last_job.current, status_history=enriched.last_job.history,
            schema_and_anchor_validation='passed', disk_roundtrip_identical=(loaded == bundle),
            chunks_unchanged=(before['chunks'] == loaded['chunks']), output=bundle_summary(loaded),
            normalization=normalization_evidence(tree, loaded),
            wiring='explicit CLI GROBID_URL/--grobid-url or Pipeline(grobid=...); default HTTP upload/arXiv disabled')
        report['passed'] = (report['published_groups'] > 0 and report['disk_roundtrip_identical'] and
            report['chunks_unchanged'] and report['status']['status'] == 'completed' and
            report['service_call']['status'] == 200 and report['normalization']['person_names_checked'] > 0)
    except Exception as error:
        report['error'] = {'type': type(error).__name__, 'message': str(error)[:1500]}
    report['docker'] = {'version': command('docker', 'version', '--format', '{{.Server.Version}}'),
        'image': command('docker', 'image', 'inspect', 'grobid/grobid:0.9.1-crf', '--format', '{{json .RepoDigests}}'),
        'service': command('docker', 'compose', '-f', 'services/docker-compose.grobid.yml', '-p', 'scholar-graph-grobid', 'ps', '--format', 'json')}
    save(report)
    print(json.dumps({key: report.get(key) for key in ('passed', 'published_groups', 'elapsed_seconds', 'normalization', 'error')}, ensure_ascii=False, indent=2))
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())

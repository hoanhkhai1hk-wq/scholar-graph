"""Fetch the official public model with checked ranges; no paper content is transmitted."""
from concurrent.futures import ThreadPoolExecutor
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import tarfile
import threading
import time

import httpx

ROOT = Path(__file__).resolve().parents[2]
parser = argparse.ArgumentParser()
parser.add_argument('--run', default='formula-download')
parser.add_argument('--resume-from')
args = parser.parse_args()
if not re.fullmatch(r'[a-z0-9-]+', args.run) or (args.resume_from and not re.fullmatch(r'[a-z0-9-]+', args.resume_from)):
    raise ValueError('Use simple evidence directory names')
OUT = ROOT / 'data/item01-20261028' / args.run
OUT.mkdir(parents=True, exist_ok=False)
URL = 'https://paddle-model-ecology.bj.bcebos.com/paddlex/official_inference_model/paddle3.0.0/PP-FormulaNet-S_infer.tar'
report = {'source': URL, 'started_at': datetime.now(timezone.utc).isoformat(), 'passed': False}
def save():
    (OUT / 'result.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
save()
started = time.monotonic()
try:
    with httpx.Client(trust_env=False, timeout=httpx.Timeout(90, connect=15), limits=httpx.Limits(max_connections=12)) as client:
        first = client.get(URL, headers={'Range': 'bytes=0-0'})
        first.raise_for_status()
        match = re.fullmatch(r'bytes 0-0/(\d+)', first.headers.get('content-range', ''))
        if first.status_code != 206 or not match:
            raise ValueError('Official server did not confirm byte ranges')
        length = int(match[1]); etag = first.headers.get('etag', '').strip('"')
        report.update(bytes=length, etag=etag, parallel_requests=12); save()
        size = 512*1024
        ranges = [(n, min(n + size, length)-1) for n in range(0, length, size)]
        previous = ROOT / 'data/item01-20261028' / args.resume_from if args.resume_from else None
        report['completed_parts'] = 0
        lock = threading.Lock()
        def download(bounds):
            start, stop = bounds
            part = OUT / f'{start:012d}.part'
            if previous:
                old_start = start // (4*1024*1024) * (4*1024*1024)
                old = previous / f'{old_start:012d}.part'
                if old.exists() and old.stat().st_size == min(4*1024*1024, length-old_start):
                    with old.open('rb') as source:
                        source.seek(start-old_start)
                        part.write_bytes(source.read(stop-start+1))
            for attempt in range(8):
                try:
                    received = part.stat().st_size if part.exists() else 0
                    if received == stop-start+1:
                        break
                    at = start+received
                    with client.stream('GET', URL, headers={'Range': f'bytes={at}-{stop}'}) as response:
                        response.raise_for_status()
                        if response.status_code != 206 or response.headers.get('content-range') != f'bytes {at}-{stop}/{length}':
                            raise ValueError('Range response mismatch')
                        if response.headers.get('etag', '').strip('"') != etag:
                            raise ValueError('Model source changed during download')
                        with part.open('ab') as stream:
                            for data in response.iter_bytes(16*1024): stream.write(data)
                    if part.stat().st_size != stop-start+1:
                        raise ValueError('Incomplete range')
                    break
                except Exception:
                    if attempt == 7:
                        return None
            with lock:
                report['completed_parts'] += 1
                if report['completed_parts'] % 30 == 0:
                    save()
                    print(json.dumps({'completed_parts':report['completed_parts'], 'total_parts':len(ranges)}), flush=True)
            return part
        with ThreadPoolExecutor(max_workers=12) as pool:
            parts = list(pool.map(download, ranges))
        if any(part is None for part in parts):
            raise ValueError('Some model ranges remain incomplete; completed parts retained')
        archive = OUT / 'PP-FormulaNet-S.tar'
        with archive.open('xb') as stream:
            for part in parts:
                with part.open('rb') as incoming:
                    while block := incoming.read(1024*1024): stream.write(block)
        digest = hashlib.md5(usedforsecurity=False)
        sha = hashlib.sha256()
        with archive.open('rb') as stream:
            while block := stream.read(1024*1024): digest.update(block); sha.update(block)
        if re.fullmatch(r'[a-fA-F0-9]{32}', etag) and digest.hexdigest().lower() != etag.lower():
            raise ValueError('Official ETag checksum mismatch')
        target = ROOT / 'data/repair-ocr-model-smoke/models/paddlex/item01-formula'
        target.mkdir(exist_ok=False)
        with tarfile.open(archive) as tar:
            for member in tar.getmembers():
                if member.issym() or member.islnk() or not (target/member.name).resolve().is_relative_to(target.resolve()):
                    raise ValueError('Unsafe model archive member')
            tar.extractall(target, filter='data')
        configs = list(target.rglob('inference.yml'))
        if len(configs) != 1: raise ValueError('Expected one formula model configuration')
        report.update(passed=True, sha256=sha.hexdigest(), model_dir=str(configs[0].parent),
                      elapsed_seconds=round(time.monotonic()-started, 3))
except Exception as error:
    report['error_type'] = type(error).__name__
finally:
    report['finished_at'] = datetime.now(timezone.utc).isoformat(); save()
print(json.dumps(report), flush=True)
raise SystemExit(0 if report['passed'] else 1)

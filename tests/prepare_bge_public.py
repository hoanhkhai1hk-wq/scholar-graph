"""Bounded anonymous HTTP range resume for the pinned public BGE-M3 weight file."""
import hashlib
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import os
from pathlib import Path
import re
import shutil
import time
import threading

import httpx

REVISION = '5617a9f61b028005a4858fdac845db406aefb181'
EXPECTED_SHA256 = 'b5e0ce3470abf5ef3831aa1bd5553b486803e83251590ab7ff35a117cf6aad38'
EXPECTED_SIZE = 2271145830
URL = f'https://huggingface.co/BAAI/bge-m3/resolve/{REVISION}/pytorch_model.bin'


def digest(path):
    value = hashlib.sha256()
    with path.open('rb') as handle:
        while block := handle.read(4*1024*1024):
            value.update(block)
    return value.hexdigest()


def main():
    started = time.perf_counter()
    root = Path(os.environ['SCHOLAR_GRAPH_BGE_M3_PATH']).resolve()
    target, partial = root/'pytorch_model.bin', root/'pytorch_model.bin.download'
    if target.exists() and target.stat().st_size == EXPECTED_SIZE and digest(target) == EXPECTED_SHA256:
        print(json.dumps({'verified':True,'already_complete':True,'sha256':EXPECTED_SHA256,'bytes':EXPECTED_SIZE}),flush=True)
        return 0
    if not partial.exists():
        candidates = [p for p in (root/'.cache/huggingface/download').glob('*.incomplete')
                      if EXPECTED_SHA256 in p.name and 0 < p.stat().st_size < EXPECTED_SIZE]
        if candidates:
            shutil.copyfile(max(candidates,key=lambda p:p.stat().st_size),partial)
        else:
            partial.touch()
    initial = partial.stat().st_size
    print(json.dumps({'stage':'public_range_preparation','revision':REVISION,'reused_container_partial_bytes':initial}),flush=True)
    parts = root/'public-range-parts'
    parts.mkdir(exist_ok=True)

    def fetch(bounds):
        start,end = bounds
        path = parts/f'{start}-{end}.part'
        if not path.exists():
            path.touch()
        if path.stat().st_size > end-start+1:
            raise ValueError('oversized cached range')
        retries=0
        with httpx.Client(follow_redirects=True,timeout=60,trust_env=False) as client:
            while path.stat().st_size < end-start+1:
                if time.perf_counter()-started > 7200:
                    raise TimeoutError('public model preparation exceeded bounded deadline')
                offset = start+path.stat().st_size
                try:
                    with client.stream('GET',URL,headers={'Range':f'bytes={offset}-{end}',
                            'Accept-Encoding':'identity','User-Agent':'ScholarGraph public model preparation'}) as response:
                        response.raise_for_status()
                        match = re.fullmatch(r'bytes (\d+)-(\d+)/(\d+)',response.headers.get('content-range',''))
                        if (response.status_code != 206 or not match or int(match[1]) != offset
                                or int(match[2]) != end or int(match[3]) != EXPECTED_SIZE):
                            raise ValueError('range response identity/offset rejected')
                        received=0
                        with path.open('ab') as handle:
                            for block in response.iter_bytes(1024*1024):
                                if time.perf_counter()-started > 7200:
                                    raise TimeoutError('public model preparation exceeded bounded deadline')
                                received+=len(block)
                                if received > end-offset+1:
                                    raise ValueError('oversized public range')
                                handle.write(block)
                        if received != end-offset+1:
                            raise ValueError('truncated public range')
                    retries=0
                except (httpx.HTTPError,OSError):
                    retries+=1
                    if retries > 8:
                        raise RuntimeError('bounded public model retries exhausted') from None
                    time.sleep(min(30,2**retries))
        return path

    ranges=[(n,min(n+64*1024*1024-1,EXPECTED_SIZE-1)) for n in range(initial,EXPECTED_SIZE,64*1024*1024)]
    completed=initial
    with ThreadPoolExecutor(max_workers=4) as pool:
        for future in as_completed([pool.submit(fetch,bounds) for bounds in ranges]):
            completed+=future.result().stat().st_size
            print(json.dumps({'stage':'public_range_progress','completed_bytes':completed,
                'total_bytes':EXPECTED_SIZE,'parallel_downloads':4,'elapsed_seconds':round(time.perf_counter()-started,3)}),flush=True)
    with partial.open('ab') as handle:
        for start,end in ranges:
            with (parts/f'{start}-{end}.part').open('rb') as part:
                shutil.copyfileobj(part,handle,1024*1024)
    actual = digest(partial)
    if actual != EXPECTED_SHA256 or partial.stat().st_size != EXPECTED_SIZE:
        raise ValueError('public weight checksum mismatch; not publishing model')
    os.replace(partial,target)
    print(json.dumps({'verified':True,'sha256':actual,'bytes':target.stat().st_size,
        'reused_container_partial_bytes':initial,'elapsed_seconds':round(time.perf_counter()-started,6)}),flush=True)
    return 0


if __name__=='__main__':
    try:
        raise SystemExit(main())
    except Exception as error:
        # Signed redirect URLs and environment values are never logged.
        print(json.dumps({'verified':False,'error_type':type(error).__name__}),flush=True)
        raise SystemExit(1)

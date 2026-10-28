"""Record observed container working-set memory/CPU without reading process environments."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import time

parser = argparse.ArgumentParser()
parser.add_argument('--output', type=Path, required=True)
parser.add_argument('--seconds', type=int, default=3600)
args = parser.parse_args()
args.output.parent.mkdir(parents=True, exist_ok=True)
if args.output.exists(): raise FileExistsError(args.output)
deadline = time.monotonic()+args.seconds
with args.output.open('x', encoding='utf-8') as stream:
    while time.monotonic() < deadline:
        try:
            result = subprocess.run(['docker', 'stats', '--no-stream', '--format', '{{json .}}', 'scholar-graph-item01-backend-1'],
                capture_output=True, text=True, timeout=15)
        except subprocess.TimeoutExpired:
            stream.write(json.dumps({'at':datetime.now(timezone.utc).isoformat(),'error':'docker_stats_timeout'})+'\n'); stream.flush()
            time.sleep(2)
            continue
        if result.returncode == 0:
            value = json.loads(result.stdout)
            row = {'at': datetime.now(timezone.utc).isoformat(), **{k:value.get(k) for k in ('CPUPerc','MemUsage','MemPerc','PIDs')}}
            stream.write(json.dumps(row)+'\n'); stream.flush()
        time.sleep(2)

"""Isolated, provenance-preserving acceptance for the selected celadon UI."""
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / 'data/ui-celadon-20261029'
API = 'http://127.0.0.1:8180'
WEB = 'http://127.0.0.1:3500'
sys.path.insert(0, str(ROOT / 'tests/item02'))
from local_environment import configured_environment

def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf8')

def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

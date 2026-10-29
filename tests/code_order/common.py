"""Targeted code-order acceptance; local sources and credentials stay private."""
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / 'data/code-order-20261029'
sys.path.insert(0, str(ROOT / 'tests/item02'))
from local_environment import configured_environment

PID = 'paper-0776f0af6f06613433bef8112cc493177534bcf42a91636c9739e789f76ec110'
API = 'http://127.0.0.1:8160'
WEB = 'http://127.0.0.1:3460'


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf8')


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

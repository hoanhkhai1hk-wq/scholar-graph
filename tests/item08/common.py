"""Item 8: isolated performance/reliability evidence, credentials never printed."""
import hashlib
import json
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
BASE=ROOT/'data/item08-20261029'
API='http://127.0.0.1:8200'
WEB='http://127.0.0.1:3520'
sys.path.insert(0,str(ROOT/'tests/item02'))
from local_environment import configured_environment

def write(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    raw=json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)
    key=configured_environment().get('DEEPSEEK_API_KEY','')
    if key and key in raw:raise RuntimeError('Credential found; report rejected')
    path.write_text(raw,encoding='utf8')

def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

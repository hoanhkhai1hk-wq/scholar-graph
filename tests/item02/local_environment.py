"""Load only this task's existing provider configuration; never print values."""
import os
from pathlib import Path

def configured_environment():
    env=dict(os.environ)
    for line in (Path(__file__).resolve().parents[2]/'.env').read_text(encoding='utf-8-sig').splitlines():
        if line.lstrip().startswith('#') or '=' not in line: continue
        name,value=line.split('=',1); name=name.strip()
        if name in {'DEEPSEEK_API_KEY','DEEPSEEK_MODEL'}:
            env[name]=value.strip().strip(chr(34)).strip(chr(39))
    return env

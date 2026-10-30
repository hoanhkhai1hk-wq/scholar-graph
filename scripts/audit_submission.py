"""Scan published files and reachable history; never print credential values."""
import argparse
import io
import json
from pathlib import Path
import re
import subprocess

ROOT=Path(__file__).resolve().parents[1]
PATTERNS={
    'provider_key':re.compile(rb'\bsk-[A-Za-z0-9_-]{20,}\b'),
    'github_token':re.compile(rb'\b(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,})\b'),
    'aws_access_key':re.compile(rb'\b(?:AKIA|ASIA)[A-Z0-9]{16}\b'),
    'private_key':re.compile(rb'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----'),
}

def git(*args):return subprocess.check_output(['git',*args],cwd=ROOT)

def configured_key():
    p=ROOT/'.env'
    for line in p.read_text(encoding='utf-8-sig').splitlines() if p.is_file() else []:
        if line.startswith('DEEPSEEK_API_KEY='):
            return line.split('=',1)[1].strip().strip('"\'').encode()
    return b''

def findings(raw,where,key):
    found=[]
    for kind,pattern in PATTERNS.items():
        for m in pattern.finditer(raw):
            found.append({'location':where,'kind':kind,'line':raw[:m.start()].count(b'\n')+1})
    if key and key in raw:found.append({'location':where,'kind':'configured_key_exact'})
    return found

def scan_pdf(raw,where,key):
    if not raw.startswith(b'%PDF-'):return []
    from pypdf import PdfReader
    text='\n'.join(p.extract_text() or '' for p in PdfReader(io.BytesIO(raw)).pages).encode()
    return findings(text,where+' (PDF text)',key)

def audit(include):
    key=configured_key();hits=[];paths=[p for p in git('ls-files','-z').decode().split('\0') if p]
    paths=sorted(set(paths+include));work_bytes=0
    for name in paths:
        p=ROOT/name
        if not p.is_file():continue
        raw=p.read_bytes();work_bytes+=len(raw);hits+=findings(raw,name,key)+scan_pdf(raw,name,key)
    stream=subprocess.Popen(['git','cat-file','--batch'],cwd=ROOT,stdin=subprocess.PIPE,stdout=subprocess.PIPE)
    history_bytes=0;history_count=0
    try:
        for line in git('rev-list','--objects','--all').decode().splitlines():
            oid,_,name=line.partition(' ')
            stream.stdin.write((oid+'\n').encode());stream.stdin.flush()
            header=stream.stdout.readline().decode().split()
            if len(header)!=3:raise RuntimeError('Cannot read Git object')
            _,kind,size=header;raw=stream.stdout.read(int(size));assert stream.stdout.read(1)==b'\n'
            if kind not in ('blob','commit','tag'):continue
            history_bytes+=len(raw);history_count+=1;where='git:'+oid+(':'+name if name else '')
            hits+=findings(raw,where,key)+scan_pdf(raw,where,key)
    finally:
        stream.stdin.close();stream.stdout.close();stream.wait()
    forbidden=[p for p in paths if p.startswith('pdf/') or (p.lower().endswith('.pdf') and p!='docs/technical-document.pdf') or p=='.env' or p.startswith('.env.') and p!='.env.example']
    return {'scope':'tracked working files + explicitly included deliverables; all reachable Git blob/commit/tag objects; extracted PDF text',
            'ignored_local_env_scanned_as_public':False,'working_files':len(paths),'working_bytes':work_bytes,
            'history_objects':history_count,'history_bytes':history_bytes,'key_pattern_hits':hits,
            'key_pattern_hit_count':len(hits),'forbidden_tracked_files':forbidden,'passed':not hits and not forbidden}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--include',nargs='*',default=[]);p.add_argument('--output',type=Path,default=ROOT/'data/submission-20261030/secret-scan.json');a=p.parse_args()
    report=audit(a.include);a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps(report,ensure_ascii=False));raise SystemExit(0 if report['passed'] else 1)

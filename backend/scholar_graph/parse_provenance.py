"""Optional operational metadata; never inserted into frozen paper records."""
import json
import os
from uuid import uuid4

from .atomic_io import windows_retry
from .storage import write_json

HEADER = 'X-ScholarGraph-Parse-Meta'


def save(root, job_id, metadata):
    parent=root/'jobs'/job_id
    parent.mkdir(parents=True,exist_ok=True)
    temporary=parent/(uuid4().hex+'.tmp')
    try:
        write_json(temporary,metadata)
        windows_retry(lambda:os.replace(temporary,parent/'parse-metadata.json'))
    finally:
        temporary.unlink(missing_ok=True)


def latest(root,paper_id):
    candidates=[]
    for path in (root/'jobs').glob('job-*/parse-metadata.json'):
        value=json.loads(path.read_text(encoding='utf-8'))
        if value.get('paper_id')==paper_id:
            candidates.append((path.stat().st_mtime_ns,path.parent.name,value))
    return max(candidates,key=lambda x:x[:2])[2] if candidates else None


def response_header(response,metadata):
    if metadata is not None:
        from urllib.parse import quote
        response.headers[HEADER]=quote(json.dumps(summary(metadata),ensure_ascii=False,allow_nan=False),safe='')


def summary(metadata):
    if metadata is None:return None
    result={k:v for k,v in metadata.items() if k!='reference_matches'}
    if 'reference_matches' in metadata:result['reference_matches_count']=len(metadata['reference_matches'])
    return result

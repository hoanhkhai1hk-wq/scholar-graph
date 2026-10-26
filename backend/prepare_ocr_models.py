"""Prepare public OCR weights without parsing PDFs or writing paper records."""
import json
import os
from pathlib import Path
import subprocess
import sys
import time


def main():
    root=Path(__file__).resolve().parents[1]
    cache=Path(os.environ.get('SCHOLAR_GRAPH_OCR_CACHE_DIR',root/'data/paddle-models')).resolve()
    cache.mkdir(parents=True,exist_ok=True)
    env={k:v for k,v in os.environ.items() if not any(s in k.upper() for s in ('API_KEY','TOKEN','SECRET','PASSWORD'))}
    env.update(PADDLE_PDX_CACHE_HOME=str(cache),PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK='True',
        PYTHONPATH=str(root/'backend'),PYTHONIOENCODING='utf-8')
    started=time.perf_counter()
    try:
        result=subprocess.run([sys.executable,'-c',
            'from scholar_graph._engine_worker import paddle_engine; paddle_engine("en")'],
            cwd=root,env=env,capture_output=True,timeout=7200)
        code=result.returncode
        error=None if code==0 else 'Public OCR model preparation failed; no PDF parsed'
    except subprocess.TimeoutExpired:
        code,error=124,'Public OCR model preparation exceeded 7200 seconds; no PDF parsed'
    metadata={'public_ocr_preparation':True,'exit_code':code,'error':error,
        'cache_directory':str(cache),'elapsed_seconds':round(time.perf_counter()-started,6),
        'weight_files':len(list(cache.rglob('*.pdiparams'))),'pdf_inputs':0}
    print(json.dumps(metadata),flush=True)
    return code


if __name__=='__main__':
    raise SystemExit(main())

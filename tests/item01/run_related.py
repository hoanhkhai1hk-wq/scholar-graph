"""Full related regression, with real local parsing/OCR and no provider credentials."""
import os
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[2]
FILES=['test_parsing.py','test_api_uploads.py','test_dedup.py','test_dedup_repair.py',
       'test_semantic_dedup.py','test_engine_cache.py','test_engine_session.py','test_page_batches.py',
       'test_pdf_files.py','test_reference_identity.py','test_grobid_evidence.py','test_grobid_default_path.py',
       'test_grobid_conversion_fix.py','test_workspace.py','test_workspace_tasks.py','test_workspace_layout.py',
       'test_workspace_formulas.py','test_item01_parsing_quality.py','test_proxy_compatibility.py']
if __name__=='__main__':
    name=sys.argv[1]
    if not name.replace('-','').isalnum(): raise ValueError('Invalid run name')
    out=ROOT/'data/item01-20261028'/name; out.mkdir(parents=True,exist_ok=False)
    env={k:v for k,v in os.environ.items() if not any(s in k.upper() for s in ('API_KEY','TOKEN','SECRET','PASSWORD'))}
    env.update(SCHOLAR_GRAPH_OCR_CACHE_DIR=str(ROOT/'data/repair-ocr-model-smoke/models/paddlex'),
               SCHOLAR_GRAPH_GROBID_ENABLED='false',SCHOLAR_GRAPH_TRACKING_ENABLED='false',PYTHONIOENCODING='utf-8')
    raise SystemExit(subprocess.run([sys.executable,'-m','pytest',*[str(ROOT/'tests'/f) for f in FILES],
        '-q','--run-ocr','--basetemp',str(out/'temp'),'--junitxml',str(out/'junit.xml')],cwd=ROOT,env=env).returncode)

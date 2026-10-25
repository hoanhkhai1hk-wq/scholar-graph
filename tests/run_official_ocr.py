"""官方 pdf/ 真文件：直接上传用户扫描件，不重制、不修改默认时限。"""
import json
import shutil
import subprocess
import time
from importlib.metadata import version
from pathlib import Path

from official_pdf_support import ROOT, prepare, header, save, file_info, upload, parsed_details
import sys
sys.path.insert(0, str(ROOT / 'backend'))
from fastapi.testclient import TestClient
from pypdf import PdfReader
from scholar_graph.api import create_app


def main():
    root = prepare(ROOT / 'data/official-pdf/ocr')
    report = ROOT / 'tests/reports/official-pdf-ocr.json'
    source = ROOT / 'pdf/1706.03762v1_img.pdf'
    result = header('ocr')
    result['source'] = file_info(source)
    with source.open('rb') as handle:
        result['text_layer_chars_by_page'] = [len((p.extract_text() or '').strip()) for p in PdfReader(handle).pages]
    records = root / 'records'
    cache_source = ROOT / 'data/module-one/models/paddlex'
    if cache_source.is_dir():
        cache = records / 'models/paddlex'
        shutil.copytree(cache_source, cache, ignore=shutil.ignore_patterns('*.lock'))
        result['model_cache'] = {'preseeded_from': str(cache_source), 'files': sum(p.is_file() for p in cache.rglob('*'))}
    result.update(default_api_configuration=True, engine_timeout_seconds=300,
                  ocr_versions={name: version(name) for name in ('paddleocr', 'paddlepaddle')}, engine_calls=[])
    original = subprocess.run

    def observe(command, *args, **kwargs):
        if not isinstance(command, list) or len(command) < 4 or not str(command[1]).endswith('_engine_worker.py'):
            return original(command, *args, **kwargs)
        event = {'mode': command[3], 'timeout_seconds': kwargs.get('timeout')}
        result['engine_calls'].append(event)
        start = time.perf_counter()
        try:
            value = original(command, *args, **kwargs)
            event['returncode'] = value.returncode
            return value
        except Exception as error:
            event['exception_type'] = type(error).__name__
            raise
        finally:
            event['elapsed_seconds'] = round(time.perf_counter() - start, 6)
            save(report, result)

    save(report, result)
    app = create_app(data_dir=records)
    with TestClient(app) as client:
        # Observe the unchanged real call and re-raise every exception; no fake engine/output.
        subprocess.run = observe
        try:
            result['upload'] = upload(client, source)
        finally:
            subprocess.run = original
        result['parsed'] = parsed_details(client, records, result['upload'])
    result['status_histories'] = [json.loads(p.read_text(encoding='utf-8')) for p in (records / 'jobs').glob('job-*/parse-status.json')]
    result['ocr_branch_entered'] = any(s['status'] == 'ocr' for h in result['status_histories'] for s in h)
    result['effective_chunks'] = sum(len(json.loads(p.read_text(encoding='utf-8'))) for p in (records / 'papers').glob('*/chunks.json'))
    result['diagnosis'] = {'source': 'backend/scholar_graph/pipeline.py:74 -> adapters.py:33-43',
        'note': 'engine_calls 仅旁观真实 subprocess.run，返回值与异常原样透传；没有记录引擎日志或环境值。失败发生于OCR worker调用，具体类别见exception_type；无法据此推断逐页进度或识别准确率。'}
    result['source_after'] = file_info(source)
    result['conclusion'] = '通过' if result['upload']['http_status'] == 201 and result['effective_chunks'] > 0 and result['ocr_branch_entered'] else '失败：官方 pdf/ 真文件扫描件未发布有效OCR Chunk。'
    save(report, result)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    main()

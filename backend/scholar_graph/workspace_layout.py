"""Real local layout regions with page checkpoints, source crops and no invented text."""
from collections import Counter
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys
import time

from fastapi import APIRouter, Query
from .errors import PipelineError
from .api_transport import paginate
from .pdf_files import PdfFiles
from .workspace_structure import crop_region

MODEL = 'PP-DocLayout-S'
REGION_TYPES = {'formula': 'formula', 'table': 'table', 'image': 'figure', 'chart': 'figure'}


def overlap_fraction(chunk_box, region_box):
    a, b = chunk_box, region_box
    area = max(0, min(a[2], b[2])-max(a[0], b[0])) * max(0, min(a[3], b[3])-max(a[1], b[1]))
    return area / max(1e-12, (a[2]-a[0])*(a[3]-a[1]))


def checked_pages(value, pages):
    if not isinstance(value, list) or [p.get('page_number') for p in value] != pages:
        raise PipelineError('VALIDATION_ERROR', '版面检测页序或覆盖范围不正确。')
    for page in value:
        if not isinstance(page.get('regions'), list) or len(page['regions']) > 1000:
            raise PipelineError('VALIDATION_ERROR', '版面区域数量不合法。')
        for region in page['regions']:
            box = region.get('bbox')
            if (set(region) != {'label', 'score', 'bbox'} or not isinstance(region['label'], str) or
                    type(region['score']) not in (int, float) or not math.isfinite(region['score']) or not .5 <= region['score'] <= 1 or
                    not isinstance(box, list) or len(box) != 4 or any(type(x) not in (float, int) or not math.isfinite(x) or not 0 <= x <= 1 for x in box) or
                    not (box[0] < box[2] and box[1] < box[3])):
                raise PipelineError('VALIDATION_ERROR', '版面区域坐标或置信度不合法。')
    return value


def layout_task(workspace, identity, parameters, runner):
    pid = parameters['paper_id']; meta = workspace.metadata(pid); count = meta['page_count']
    pdf = PdfFiles(workspace.root).locate(pid)
    completed, cache_hits, started = [], 0, time.monotonic()
    for start in range(1, count + 1, 16):
        if runner.cancelled(identity): break
        pages = list(range(start, min(start+16, count+1)))
        missing = []
        for page in pages:
            cached = workspace.read('layout_page', f'{pid}-p{page:04d}')
            if cached and cached.get('file_hash') == meta['file_hash'] and cached.get('model') == MODEL and cached.get('revision') == 1:
                completed.append(page); cache_hits += 1
            else: missing.append(page)
        runner.progress(identity, len(completed), count, f'正在检测第 {start}–{pages[-1]} 页的真实版面区域；按批次保存检查点')
        if missing:
            if time.monotonic()-started > 1800:
                raise PipelineError('PARSE_FAILED', '版面检测超过总时限；已检测页面保留，可重试恢复。')
            env = dict(os.environ)
            env.update(PADDLE_PDX_CACHE_HOME=os.environ.get('SCHOLAR_GRAPH_OCR_CACHE_DIR', str(workspace.root/'models/paddlex')),
                       PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK='True', PADDLE_PDX_MODEL_SOURCE='BOS')
            try:
                result = subprocess.run([sys.executable, str(Path(__file__).with_name('_layout_worker.py')), str(pdf), json.dumps(missing)],
                                        capture_output=True, env=env, timeout=120, check=False)
                if result.returncode or len(result.stdout) > 8*1024*1024: raise ValueError()
                detected = checked_pages(json.loads(result.stdout), missing)
            except Exception:
                raise PipelineError('PARSE_FAILED', '本地版面模型未完成；请检查模型缓存或运行时限，已完成页面可恢复。') from None
            for page in detected:
                workspace.put('layout_page', f'{pid}-p{page["page_number"]:04d}', {
                    **page, 'paper_id': pid, 'file_hash': meta['file_hash'], 'model': MODEL, 'revision': 1}, 'layout_page_detected')
                completed.append(page['page_number'])
        output = {'paper_id': pid, 'model': MODEL, 'completed_pages': sorted(completed), 'expected_pages': count,
                  'complete': len(completed) == count, 'cache_hits': cache_hits,
                  'succeeded_count': len(completed), 'failed_count': 0,
                  'notice': '区域是本地模型检测结果，保留原文图像；不把区域检测说成公式LaTeX或完整表格单元格识别。'}
        runner.update(identity, result=output)
        runner.progress(identity, len(completed), count, f'已检测 {len(completed)} / {count} 页，原始文字和PDF保留')
    if completed:
        from .front_matter import apply_local_front_matter
        apply_local_front_matter(workspace, pid)
    return output if completed else {'succeeded_count': 0, 'failed_count': 0}


def layout_routes(workspace, tasks):
    router = APIRouter(prefix='/api/v2')
    tasks.handlers['layout'] = lambda identity, parameters, runner: layout_task(workspace, identity, parameters, runner)

    @router.post('/papers/{paper_id}/layout-tasks', status_code=202)
    def submit(paper_id: str):
        workspace.metadata(paper_id)
        return tasks.submit('layout', {'paper_id': paper_id})

    @router.get('/papers/{paper_id}/layout')
    def regions(paper_id: str, page: int = Query(1, ge=1), kind: str | None = None):
        workspace.metadata(paper_id)
        records = workspace.layout_pages(paper_id)
        items = []
        for record in records:
            for index, region in enumerate(record['regions']):
                if region['label'] in ('text', 'number', 'header', 'footer', 'aside_text', 'footnote'): continue
                items.append({**region, 'id': f'p{record["page_number"]:04d}-r{index:04d}', 'page_number': record['page_number'],
                              'source_chunk_ids': [], 'source_text': ''})
        counts = dict(Counter(item['label'] for item in items))
        paged = paginate([item for item in items if kind is None or item['label'] == kind], page, 12)
        page_chunks = {}
        for chunk in workspace.bundle(paper_id)['chunks']:
            page_chunks.setdefault(chunk['page_number'], []).append(chunk)
        for item in paged['items']:
            matching = [c for c in page_chunks.get(item['page_number'], []) if c['bbox'] and overlap_fraction(c['bbox'], item['bbox']) >= .5]
            item.update(source_chunk_ids=[c['chunk_id'] for c in matching], source_text='\n'.join(c['text'] for c in matching))
        return {'model': MODEL, 'detected_pages': len(records), 'expected_pages': workspace.metadata(paper_id)['page_count'],
                'counts': counts, 'regions': paged}

    @router.get('/papers/{paper_id}/layout-regions/{region_id}')
    def image(paper_id: str, region_id: str):
        workspace.metadata(paper_id)
        match = re.fullmatch(r'p(\d{4})-r(\d{4})', region_id)
        if not match: raise PipelineError('PAPER_NOT_FOUND', '没有该原文区域。')
        page, index = map(int, match.groups())
        record = workspace.read('layout_page', f'{paper_id}-p{page:04d}')
        if not record or index >= len(record['regions']): raise PipelineError('PAPER_NOT_FOUND', '没有该原文区域。')
        return crop_region(workspace, paper_id, page, record['regions'][index]['bbox'])
    return router

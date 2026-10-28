"""Bounded physical-page parsing with validated incremental publication and checkpoints."""
import json
import os
import time
from dataclasses import dataclass
from pathlib import Path

import pypdfium2 as pdfium

from .chunk_index import ChunkIndex
from .errors import PipelineError
from .normalize import normalize, block_text, reference_entries, citation_links
from .storage import write_json
from .atomic_io import windows_retry


@dataclass(frozen=True)
class ParseLimits:
    max_pages: int = 2000
    text_batch_pages: int = 32
    page_timeout: int = 90
    batch_timeout: int = 120
    total_timeout: int = 1800

    @classmethod
    def environment(cls):
        defaults = cls()
        try:
            value = cls(**{name: int(os.environ.get('SCHOLAR_GRAPH_' + name.upper(), getattr(defaults, name)))
                           for name in cls.__dataclass_fields__})
            if not (1 <= value.max_pages <= 10000 and 1 <= value.text_batch_pages <= 128
                    and 1 <= value.page_timeout <= 600 and 1 <= value.batch_timeout <= 600
                    and 1 <= value.total_timeout <= 7200):
                raise ValueError
            return value
        except ValueError:
            raise PipelineError('VALIDATION_ERROR', '页面批次/时限配置超出允许范围。') from None


def parse_batches(pipeline, snapshot, paper, ocr_pages):
    store, gate, job, engines, limits = pipeline.store, pipeline.gate, pipeline.last_job, pipeline.engines, pipeline.limits
    partial = store.root / 'partial' / paper['id']
    checkpoint = partial / 'progress.json'
    completed, chunks, failures, batches, index_seconds = set(), [], [], 0, 0.0
    if checkpoint.exists():
        previous = json.loads(checkpoint.read_text(encoding='utf-8'))
        completed = set(previous['completed_pages'])
    if list(partial.glob('batch-*')):
        chunks = store.partial(paper['id'])['chunks']
        completed.update(c['page_number'] for c in chunks)
        batches = len(list(partial.glob('batch-*')))
    index = ChunkIndex(store.root, paper['id'])
    if chunks:
        index.append(chunks, reset=True)  # Repair a crash between durable batch and index/checkpoint.
    started = time.monotonic()
    metrics = {'parser': 'MinerU text batches + PaddleOCR page fallback', 'limits': vars(limits),
               'completed_pages': sorted(completed), 'failed_pages': [], 'empty_pages': [],
               'batches': [], 'published_chunks': len(chunks), 'indexing_seconds': 0.0,
               'resumed_pages': len(completed)}
    pipeline.last_metrics = metrics
    if ocr_pages:
        job.move('ocr', '逐页OCR；完成页即时校验发布', progress=10)

    def persist():
        partial.mkdir(parents=True, exist_ok=True)
        metrics.update(completed_pages=sorted(completed), failed_pages=failures,
                       published_chunks=len(chunks), indexing_seconds=round(index_seconds, 6))
        if getattr(engines, '_session_enabled', False):
            metrics['engine_session'] = dict(engines.session_metrics)
        temporary = checkpoint.with_suffix('.tmp')
        write_json(temporary, metrics)
        windows_retry(lambda: os.replace(temporary, checkpoint))
        if callable(getattr(pipeline, 'on_page_progress', None)):
            pipeline.on_page_progress(len(completed), paper['page_count'])

    def publish(pages, mode):
        nonlocal batches, index_seconds
        begin = time.monotonic()
        preceding = [c for c in chunks if c['page_number'] <= min(p['page_idx'] for p in pages)]
        preceding.sort(key=lambda c: (c['page_number'], c['chunk_id']))
        bundle = normalize({'pages': pages}, None, paper, [], start_index=len(chunks),
                           section_path=preceding[-1]['section_path'] if preceding else [], include_references=False)
        if bundle['chunks']:
            gate.bundle(bundle)
            batches += 1
            store.partial_batch(bundle, batches)
            index.append(bundle['chunks'])
            chunks.extend(bundle['chunks'])
        index_seconds += time.monotonic() - begin
        physical = [page['page_idx'] + 1 for page in pages]
        completed.update(physical)
        metrics['empty_pages'].extend(page['page_idx'] + 1 for page in pages if not any(
            block_text(b.get('content')).strip() for b in page.get('blocks', [])))
        metrics['batches'].append({'mode': mode, 'pages': physical, 'chunks': len(bundle['chunks']),
                                   'cumulative_chunks': len(chunks)})
        persist()
        progress = min(75, 10 + 65 * (len(completed) + len(failures)) // paper['page_count'])
        job.move(job.current['status'], f'已处理{len(completed)}/{paper["page_count"]}页，已发布{len(chunks)}个Chunk；失败页{[f["page_number"] for f in failures]}', progress=progress)

    def timeout(seconds):
        remaining = limits.total_timeout - (time.monotonic() - started)
        if remaining <= 0:
            raise PipelineError('OCR_FAILED', '达到整篇解析时限。')
        return min(seconds, remaining)

    def ocr_one(page_index):
        if callable(getattr(pipeline, 'cancel_requested', None)) and pipeline.cancel_requested():
            persist()
            raise PipelineError('PARSE_FAILED', '已停止解析；已完成页和原始输入保留，重试将从检查点恢复。')
        if job.current['status'] == 'parsing':
            job.move('ocr', 'MinerU批次未完成，逐页PaddleOCR兜底')
        try:
            value = engines.ocr(snapshot, [page_index], timeout=timeout(limits.page_timeout))
            if isinstance(value.get('ocr_metadata'), dict):
                metrics['ocr_metadata'] = value['ocr_metadata']
            pages = value.get('pages')
            if (not isinstance(pages, list) or len(pages) != 1 or not isinstance(pages[0], dict)
                    or type(pages[0].get('page_idx')) is not int or pages[0]['page_idx'] != page_index or not any(
                    block_text(b.get('content')).strip() for b in pages[0].get('blocks', []))):
                raise PipelineError('OCR_FAILED', '页面未返回可验证OCR文本。')
        except PipelineError as error:
            failures.append({'page_number': page_index + 1, 'error_code': error.code, 'message': error.message})
            persist()
        else:
            publish(pages, 'paddleocr')

    document = pdfium.PdfDocument(snapshot)
    try:
        cursor = 0
        while cursor < paper['page_count']:
            if callable(getattr(pipeline, 'cancel_requested', None)) and pipeline.cancel_requested():
                persist()
                raise PipelineError('PARSE_FAILED', '已停止解析；已完成页和原始输入保留，重试将从检查点恢复。')
            if cursor + 1 in completed:
                cursor += 1
                continue
            if time.monotonic() - started >= limits.total_timeout:
                failures.extend({'page_number': n + 1, 'error_code': 'PARSE_FAILED', 'message': '达到整篇解析时限，未处理此页。'}
                                for n in range(cursor, paper['page_count']) if n + 1 not in completed)
                persist()
                break
            if cursor in ocr_pages:
                ocr_one(cursor)
                cursor += 1
                continue
            group = []
            while cursor < paper['page_count'] and len(group) < limits.text_batch_pages and cursor not in ocr_pages:
                if cursor + 1 not in completed:
                    group.append(cursor)
                cursor += 1
            if not group:
                continue
            batch_path = snapshot.parent / 'text-batch.pdf'
            part = pdfium.PdfDocument.new()
            try:
                part.import_pages(document, group)
                part.save(batch_path)
            finally:
                part.close()
            try:
                native = engines.text(batch_path, timeout=timeout(limits.batch_timeout))
                pages = native['pages']
                indices = [p.get('page_idx') for p in pages]
                if (native.get('schema') != 'docvortex.middle' or native.get('is_full_document') is not True
                        or any(type(n) is not int for n in indices) or sorted(indices) != list(range(len(group)))):
                    raise PipelineError('PARSE_FAILED', 'MinerU批次物理页覆盖不完整。')
                for page in pages:
                    page['page_idx'] = group[page['page_idx']]
            except PipelineError:
                for n in group:
                    ocr_one(n)
            else:
                publish(pages, 'mineru')
    finally:
        document.close()
    persist()
    if failures:
        failed_pages = [row['page_number'] for row in failures]
        raise PipelineError('OCR_FAILED' if any(p - 1 in ocr_pages for p in failed_pages) else 'PARSE_FAILED',
                            f'解析未完成；失败物理页：{failed_pages}。已保留{len(chunks)}个合规Chunk。',
                            details={'paper_id': paper['id'], 'failed_pages': ','.join(map(str, failed_pages)),
                                     'page_errors': '; '.join(f'{f["page_number"]}:{f["error_code"]}:{f["message"]}' for f in failures),
                                     'published_chunks': len(chunks), 'chunks_url': f'/api/v1/papers/{paper["id"]}/chunks'})
    chunks.sort(key=lambda c: (c['page_number'], c['chunk_id']))
    if metrics['resumed_pages']:
        begin = time.monotonic()
        index.append(chunks, reset=True)
        index_seconds += time.monotonic() - begin
        persist()
    refs = reference_entries(chunks, paper['id'])
    return {'paper_meta': paper, 'chunks': chunks, 'reference_entries': refs, 'citation_links': citation_links(chunks, refs)}

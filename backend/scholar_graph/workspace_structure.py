"""Inspectable parsed structure, source-region images and audited classification corrections."""
from collections import Counter
import io
import math
from typing import Literal

from fastapi import APIRouter, Query
from pydantic import BaseModel, ConfigDict, Field
from starlette.responses import Response

from .api_transport import paginate
from .errors import PipelineError
from .pdf_files import PdfFiles
from .parse_provenance import latest, summary
from .validation import chunk_anchor
from .heading_rules import post_reference_heading


class ClassificationPatch(BaseModel):
    model_config = ConfigDict(extra='forbid')
    type: Literal['text', 'table', 'figure', 'formula']
    section_path: list[str] = Field(max_length=3)
    note: str = Field(min_length=1, max_length=1000)


def structure_routes(workspace):
    router = APIRouter(prefix='/api/v2')

    @router.get('/papers/{paper_id}/structure')
    def structure(paper_id: str, kind: Literal['text', 'table', 'figure', 'formula'] | None = None,
                  page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=50)):
        bundle = workspace.bundle(paper_id)
        counts = Counter(c['type'] for c in bundle['chunks'])
        items = [{'chunk_id': c['chunk_id'], 'text': c['text'], 'page_number': c['page_number'],
                  'type': c['type'], 'section_path': c['section_path'], 'anchor': chunk_anchor(c),
                  'has_source_region': bool(c['bbox']), 'correction': workspace.read('classification', c['chunk_id'])}
                 for c in bundle['chunks'] if kind is None or c['type'] == kind]
        return {'metadata': workspace.paper(paper_id), 'counts': dict(counts),
                'reference_count': len(bundle['reference_entries']),
                'appendix_chunks': sum(any('appendix' in h.casefold() or '附录' in h or post_reference_heading(h)
                                          for h in c['section_path']) for c in bundle['chunks']),
                'parse': summary(latest(workspace.root, paper_id)), 'chunks': paginate(items, page, page_size)}

    @router.get('/papers/{paper_id}/regions/{chunk_id}')
    def region(paper_id: str, chunk_id: str):
        bundle = workspace.bundle(paper_id)
        chunk = next((c for c in bundle['chunks'] if c['chunk_id'] == chunk_id), None)
        if not chunk or not chunk['bbox']:
            raise PipelineError('PAPER_NOT_FOUND', '该段没有可核验的原文区域，请打开 PDF 查看。')
        return crop_region(workspace, paper_id, chunk['page_number'], chunk['bbox'])

    @router.patch('/papers/{paper_id}/structure/{chunk_id}')
    def classify(paper_id: str, chunk_id: str, body: ClassificationPatch):
        original = next((c for c in workspace.repository.paper(paper_id)['chunks'] if c['chunk_id'] == chunk_id), None)
        if not original:
            raise PipelineError('PAPER_NOT_FOUND', '没有找到需要修正的原文段落。')
        if any(not title.strip() or len(title) > 500 for title in body.section_path):
            raise PipelineError('VALIDATION_ERROR', '章节标题须为非空文本且每级不超过五百字符。')
        value = {'paper_id': paper_id, 'chunk_id': chunk_id, **body.model_dump(), 'source': 'user_classification_correction',
                 'original_type': original['type'], 'original_section_path': original['section_path']}
        workspace.put('classification', chunk_id, value, 'classification_corrected')
        return value
    return router


def crop_region(workspace, paper_id, page_number, box):
    import pypdfium2 as pdfium
    document = pdfium.PdfDocument(PdfFiles(workspace.root).locate(paper_id))
    page = document[page_number - 1]
    bitmap = None
    try:
        scale = min(2, math.sqrt(16_000_000 / max(1, page.get_width() * page.get_height())))
        bitmap = page.render(scale=scale)
        image = bitmap.to_pil()
        x0, y0, x1, y1 = box
        crop = image.crop((round(x0 * image.width), round(y0 * image.height), round(x1 * image.width), round(y1 * image.height)))
        if crop.width <= 0 or crop.height <= 0:
            raise PipelineError('VALIDATION_ERROR', '原文区域坐标无效，不能生成预览。')
        output = io.BytesIO(); crop.save(output, format='PNG'); crop.close(); image.close()
        return Response(output.getvalue(), media_type='image/png', headers={'Cache-Control': 'private, max-age=3600', 'X-Content-Type-Options': 'nosniff'})
    finally:
        if bitmap is not None: bitmap.close()
        page.close(); document.close()

"""Resumable translation over every source chunk, including long books.

Only validated batches enter the cache. A stopped/failed run cannot claim full
coverage. A retry reuses batches with the exact same source digest and direction.
"""
import hashlib
import json
import re
import uuid
from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict, Field, model_validator

from .errors import PipelineError
from .translation import Translator, select_chunks, render_markdown, check_terms


class TranslationTaskRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    scope: Literal['abstract', 'section', 'selection', 'full']
    target: Literal['zh', 'en'] = 'zh'
    section_path: list[str] | None = Field(default=None, min_length=1, max_length=20)
    chunk_ids: list[str] | None = Field(default=None, min_length=1, max_length=20000)
    chinese_task_id: str | None = None

    @model_validator(mode='after')
    def shape(self):
        if (self.scope == 'section') != (self.section_path is not None) or (self.scope == 'selection') != (self.chunk_ids is not None):
            raise ValueError('请选择对应的章节或段落。')
        if self.target == 'en' and self.scope not in ('abstract', 'full'):
            raise ValueError('中译英支持摘要或全文。')
        if self.target == 'zh' and self.chinese_task_id:
            raise ValueError('英译中不接受中文任务。')
        return self


def selected_chunks(bundle, request):
    # Bound batches instead of bounding the entire book. Preserve v1 limits.
    if request['scope'] == 'full':
        return bundle['chunks']
    return select_chunks(bundle, request['scope'], request.get('section_path'), request.get('chunk_ids'))


def translation_task(workspace, identity, parameters, runner):
    paper_id = parameters['paper_id']
    snapshot = workspace.read('translation_source', parameters.get('source_snapshot_id', ''))
    bundle = snapshot['bundle'] if snapshot else {**workspace.repository.paper(paper_id), 'paper_meta': workspace.paper(paper_id)['paper']}
    selected = selected_chunks(bundle, parameters)
    if not selected:
        raise PipelineError('VALIDATION_ERROR', '该范围没有可翻译的正文。')
    chinese = None
    if parameters.get('chinese_task_id'):
        task = workspace.read('task', parameters['chinese_task_id'])
        chinese = ((task or {}).get('result') or {}).get('translation')
        if not chinese or chinese['paper_id'] != paper_id or chinese['target'] != 'zh':
            raise PipelineError('VALIDATION_ERROR', '请选择同篇论文已校验的中文翻译任务。')
    batches, current, size = [], [], 0
    for chunk in selected:
        if current and size + len(chunk['text']) > 8000:
            batches.append(current)
            current, size = [], 0
        current.append(chunk)
        size += len(chunk['text'])
    if current:
        batches.append(current)
    segments, failures, calls, cache_hits, glossary = [], [], [], 0, {}
    if chinese and isinstance(chinese.get('metadata', {}).get('terminology'), dict):
        glossary = {target: source for source, target in chinese['metadata']['terminology'].items()
                    if isinstance(target, str) and not re.fullmatch(r'[\u3400-\u9fff]', target)}
    for index, batch in enumerate(batches):
        if runner.cancelled(identity):
            break
        runner.progress(identity, len(segments) + sum(f['chunk_count'] for f in failures), len(selected), f"正在翻译第 {batch[0]['page_number']}–{batch[-1]['page_number']} 页；已校验结果会保存")
        # The cache key includes all provenance-bearing input, never only a title.
        chinese_input = {**chinese, 'segments': [s for s in chinese['segments'] if s['source_chunk_id'] in {c['chunk_id'] for c in batch}]} if chinese else None
        digest = hashlib.sha256(json.dumps([paper_id, parameters['target'], batch, chinese_input['segments'] if chinese_input else None, glossary], ensure_ascii=False, sort_keys=True).encode()).hexdigest()
        response = workspace.read('translation_batch', digest)
        try:
            if response is None:
                class BatchRepository:
                    gate = workspace.repository.gate
                    def paper(self, _):
                        return {**bundle, 'chunks': batch}
                response = Translator(BatchRepository(), glossary=glossary).translate(paper_id, scope='full', target=parameters['target'], source_translation=chinese_input)
                calls.extend(response['metadata']['model_calls'])
            else:
                cache_hits += 1
            next_glossary = response['metadata'].get('terminology', {})
            if isinstance(next_glossary, dict):
                for prior in segments:
                    check_terms(prior['source_text'], prior['translated_text'], next_glossary)
                glossary = next_glossary
            workspace.put('translation_batch', digest, response)
            segments.extend(response['segments'])
        except PipelineError as error:
            failures.append({'filename': f"第 {batch[0]['page_number']}–{batch[-1]['page_number']} 页", 'chunk_count': len(batch), **error.envelope()})
        coverage = len(segments)
        result = {'translation': {'paper_id': paper_id, 'scope': parameters['scope'], 'target': parameters['target'],
                  'segments': list(segments), 'markdown': None,
                  'metadata': {'provider': 'deepseek', 'model': response['metadata']['model'] if response else None,
                    'model_calls': list(calls), 'terminology': dict(glossary), 'alignment': 'one_source_chunk_one_segment',
                    'layout_source': 'validated_original_chunks', 'cache_hits': cache_hits,
                    'expected_segments': len(selected), 'translated_segments': coverage, 'complete': coverage == len(selected)}},
                  'failed': list(failures), 'failed_count': len(failures), 'succeeded_count': coverage}
        runner.update(identity, result=result)
        runner.progress(identity, coverage + sum(f['chunk_count'] for f in failures), len(selected), f'已校验 {coverage} / {len(selected)} 个原文段落')
    if segments and len(segments) == len(selected) and parameters['scope'] == 'full':
        result['translation']['markdown'] = render_markdown(bundle, segments)
    return result if segments or failures else {'succeeded_count': 0, 'failed_count': 0}


def translation_task_routes(workspace, tasks):
    router = APIRouter(prefix='/api/v2')
    tasks.handlers['translation'] = lambda identity, parameters, runner: translation_task(workspace, identity, parameters, runner)

    @router.post('/papers/{paper_id}/translation-tasks', status_code=202)
    def translate(paper_id: str, body: TranslationTaskRequest):
        bundle = workspace.bundle(paper_id)
        if body.target == 'en' and body.chinese_task_id:
            prior = workspace.read('task', body.chinese_task_id)
            translation = ((prior or {}).get('result') or {}).get('translation')
            if not translation or translation['paper_id'] != paper_id or translation['target'] != 'zh':
                raise PipelineError('VALIDATION_ERROR', '请选择同篇论文已保存的中文译文。')
            snapshot = workspace.read('translation_source', prior.get('parameters', {}).get('source_snapshot_id', ''))
            bundle = snapshot['bundle'] if snapshot else {**workspace.repository.paper(paper_id), 'paper_meta': workspace.paper(paper_id)['paper']}
        selected = selected_chunks(bundle, body.model_dump())
        snapshot_id = uuid.uuid4().hex
        workspace.put('translation_source', snapshot_id, {'paper_id': paper_id,
                      'bundle': {**bundle, 'chunks': selected}}, 'translation_source_snapshotted')
        return tasks.submit('translation', {'paper_id': paper_id, **body.model_dump(), 'source_snapshot_id': snapshot_id})

    return router

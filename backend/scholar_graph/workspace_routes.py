"""Additive v2 routes; old records and v1 wire formats remain intact."""
from typing import Annotated, Literal
import asyncio
import json

from fastapi import APIRouter, Query, Request
from pydantic import BaseModel, ConfigDict, Field, StringConstraints
from starlette.responses import StreamingResponse
from starlette.concurrency import run_in_threadpool

from .errors import PipelineError
from .qa_sse import answer_stream, comparison_stream
from .translation import Translator
from .grobid import GrobidClient
from .grobid_enrichment import merge
from .pdf_files import PdfFiles
from .author_metadata import source_author_profiles
from .workspace_repository import WorkspaceRepository
from .normalize import reference_entries, citation_links
from .graph_service import build_graph
import hashlib
import re
import os
import threading


class MetadataPatch(BaseModel):
    model_config = ConfigDict(extra='forbid')
    title: str | None = Field(default=None, max_length=2000)
    authors: list[str] | None = Field(default=None, max_length=100)
    institutions: list[str] | None = Field(default=None, max_length=100)
    abstract: str | None = Field(default=None, max_length=100000)
    year: int | None = Field(default=None, ge=1, le=9999)


class VersionChoice(BaseModel):
    model_config = ConfigDict(extra='forbid')
    choice: Literal['keep_old', 'keep_new', 'keep_both']


class AuthorMapping(BaseModel):
    model_config = ConfigDict(extra='forbid')
    name: str = Field(min_length=1, max_length=300)
    institutions: list[str] = Field(max_length=20)
    emails: list[str] = Field(max_length=20)


class AuthorMappings(BaseModel):
    model_config = ConfigDict(extra='forbid')
    profiles: list[AuthorMapping] = Field(min_length=1, max_length=100)
    note: str = Field(min_length=1, max_length=1000)


class SessionRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    paper_ids: list[str] = Field(min_length=1, max_length=10)


class MessageRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    question: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)]


class SelectionRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    text: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=4000)]
    page_number: int = Field(ge=1, strict=True)
    target: Literal['zh'] = 'zh'


def workspace_routes(workspace):
    router = APIRouter(prefix='/api/v2')
    question_slots = threading.BoundedSemaphore(2)

    @router.get('/system')
    def system(request: Request):
        return {**workspace.system(), 'tracking_enabled': request.app.state.tracking_scheduler.config.enabled}

    @router.get('/papers')
    def papers(page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
               title: str | None = None, archived: bool = False, year: int | None = None, source: str | None = None):
        return workspace.papers(page=page, page_size=page_size, title=title, archived=archived, year=year, source=source)

    @router.get('/graph')
    def graph(paper_ids: list[str] = Query(..., min_length=1, max_length=100)):
        if len(set(paper_ids)) != len(paper_ids):
            raise PipelineError('VALIDATION_ERROR', '请选择不同的论文。')
        return build_graph([workspace.bundle(pid) for pid in paper_ids], workspace.repository.gate,
                           year_bases={pid:workspace.paper(pid)['year_source'] for pid in paper_ids})

    @router.get('/papers/{paper_id}')
    def paper(paper_id: str):
        return workspace.paper(paper_id)

    @router.patch('/papers/{paper_id}')
    def correct(paper_id: str, body: MetadataPatch):
        patch = body.model_dump(exclude_unset=True)
        if any(patch.get(field, []) is None for field in ('authors', 'institutions')):
            raise PipelineError('VALIDATION_ERROR', '作者和机构须使用数组。')
        return workspace.update(paper_id, patch)

    @router.delete('/papers/{paper_id}')
    def archive(paper_id: str):
        return workspace.archive(paper_id, True)

    @router.patch('/papers/{paper_id}/author-profiles')
    def author_mappings(paper_id: str, body: AuthorMappings):
        view = workspace.paper(paper_id)
        if [profile.name for profile in body.profiles] != view['paper']['authors']:
            raise PipelineError('VALIDATION_ERROR', '作者名称与顺序须与当前作者名单一致；请先在论文库修正名单。')
        for profile in body.profiles:
            if (any(not org.strip() or len(org) > 500 for org in profile.institutions) or
                    any(not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', email) or len(email) > 320 for email in profile.emails)):
                raise PipelineError('VALIDATION_ERROR', '机构须为非空文本，邮箱须使用有效格式。')
        with workspace.lock:
            prior = {p['name']: p for p in view['author_profiles']}
            profiles = [{**profile.model_dump(), 'order': index,
                         'anchors': prior.get(profile.name, {}).get('anchors', []),
                         'source': 'user_author_mapping', 'review_status': 'manual_mapping_not_automatic_source_proof',
                         'note': body.note} for index, profile in enumerate(body.profiles, 1)]
            state = workspace.read('paper', paper_id, {})
            state['author_profiles'] = profiles
            workspace.put('paper', paper_id, state, 'author_mappings_corrected')
        return workspace.paper(paper_id)

    @router.post('/papers/{paper_id}/restore')
    def restore(paper_id: str):
        return workspace.archive(paper_id, False)

    @router.post('/papers/{paper_id}/enrich')
    def enrich(paper_id: str):
        from .front_matter import apply_local_front_matter
        recovered = apply_local_front_matter(workspace, paper_id)
        bundle = workspace.bundle(paper_id)
        # Rebuild missing bibliography formats into an operational sidecar only.
        local_references = reference_entries(bundle['chunks'], paper_id)
        if local_references:
            bundle = {**bundle, 'reference_entries': local_references,
                      'citation_links': citation_links(bundle['chunks'], local_references)}
        if not bundle['paper_meta']['has_text_layer'] or bundle['paper_meta']['page_count'] > 100:
            return {**workspace.paper(paper_id), 'enrichment_notice': '已从本地首栏文字补齐可取证的信息。' if recovered else
                    '已检查本地首栏，没有新的可自动补齐字段；缺失项可结合原文手工填写。'}
        client = GrobidClient(os.environ.get('GROBID_URL', 'http://127.0.0.1:8070'), timeout=60)
        raw = PdfFiles(workspace.root).locate(paper_id).read_bytes()
        try:
            remote = client.enrich(bundle, raw)
        except PipelineError:
            if recovered:
                return workspace.paper(paper_id)
            raise
        enriched, details = merge(bundle, remote, workspace.repository.gate)
        patch = {key: enriched['paper_meta'][key] for key in ('title', 'authors', 'institutions', 'abstract') if enriched['paper_meta'][key]}
        profiles = source_author_profiles(bundle, patch.get('authors', []))
        if profiles:
            patch['authors'] = [p['name'] for p in profiles]
            patch['institutions'] = list(dict.fromkeys(org for p in profiles for org in p['institutions']))
        if not patch:
            raise PipelineError('UPSTREAM_ERROR', '解析服务未提取到可补齐的信息，原记录未改动。')
        workspace.update(paper_id, patch)
        workspace.put('enrichment', paper_id, {'references': enriched['reference_entries'], 'citation_links': enriched['citation_links']}, 'bibliography_enriched')
        with workspace.lock:
            value = workspace.read('paper', paper_id, {})
            value.update(author_profiles=profiles, metadata_source='grobid_enrichment_source_matched', enrichment_details=details)
            workspace.put('paper', paper_id, value, 'metadata_enriched')
            workspace.put('enrichment_diagnostics', paper_id, {'raw_header_profiles': getattr(client, 'last_author_profiles', [])})
        return workspace.paper(paper_id)

    @router.post('/papers/{paper_id}/version-choice')
    def version_choice(paper_id: str, body: VersionChoice):
        return workspace.choose_version(paper_id, body.choice)

    @router.get('/papers/{paper_id}/versions')
    def versions(paper_id: str):
        return workspace.version_info(paper_id)

    @router.get('/papers/{paper_id}/reading')
    def reading(paper_id: str, physical_page: int = Query(1, ge=1), include_navigation: bool = True):
        return workspace.reading(paper_id, physical_page, include_navigation)

    @router.get('/papers/{paper_id}/evidence/{chunk_id}')
    def evidence(paper_id: str, chunk_id: str):
        bundle = workspace.repository.paper(paper_id)
        chunk = next((c for c in bundle['chunks'] if c['chunk_id'] == chunk_id), None)
        if chunk is None:
            raise PipelineError('PAPER_NOT_FOUND', '没有找到该论文中的证据段落。')
        return chunk

    @router.post('/sessions', status_code=201)
    def session(body: SessionRequest):
        return workspace.session(body.paper_ids)

    @router.post('/papers/{paper_id}/translate-selection')
    def translate_selection(paper_id: str, body: SelectionRequest):
        bundle = workspace.bundle(paper_id)
        normalized = lambda text: re.sub(r'\s+', '', text).casefold()
        needle = normalized(body.text)
        source = next((c for c in bundle['chunks'] if c['page_number'] == body.page_number and needle in normalized(c['text'])), None)
        if source is None:
            raise PipelineError('VALIDATION_ERROR', '选中文字未匹配到该页的解析原文，请改用文本视图或整段翻译。')
        key = hashlib.sha256(json.dumps([paper_id, source['chunk_id'], body.text, body.target], ensure_ascii=False).encode()).hexdigest()
        cached = workspace.read('selection_translation', key)
        if cached:
            cached['translation']['metadata']['cache_hit'] = True
            return cached
        class SelectionRepository:
            gate = workspace.repository.gate
            def paper(self, identity):
                return {**bundle, 'chunks': [{**source, 'text': body.text}]}
        result = Translator(SelectionRepository()).translate(paper_id, scope='selection', chunk_ids=[source['chunk_id']])
        value = {'translation': result, 'selection': {'paper_id': paper_id, 'page_number': body.page_number, 'chunk_id': source['chunk_id'], 'text': body.text}}
        workspace.put('selection_translation', key, value)
        return value

    @router.get('/sessions/{session_id}')
    def get_session(session_id: str):
        return workspace.get_session(session_id)

    @router.post('/sessions/{session_id}/messages/stream')
    async def message(session_id: str, body: MessageRequest):
        session = await run_in_threadpool(workspace.get_session, session_id)
        # Never turn an earlier false numeric premise into the current question.
        previous = [m['question'] for m in session['messages'][-4:] if m.get('question')]
        question = body.question
        if previous and re.search(r'其中|这个|这些|上述|刚才|那[个些]|它|\b(?:it|that|those|they)\b', question, re.I):
            topics = re.findall(r'[A-Za-z][A-Za-z-]{1,30}|[\u4e00-\u9fff]{2,12}', previous[-1])
            question = (question + '\n仅用于消解指代的上一问题主题词：' + ' '.join(topics))[:2000]
        ids = session['paper_ids']
        repository = WorkspaceRepository(workspace)
        if not question_slots.acquire(blocking=False):
            raise PipelineError('VALIDATION_ERROR', '已有两个研究问答正在处理，请稍后重试。')
        try:
            if os.environ.get('SCHOLAR_GRAPH_QA_MODE') == 'deepseek' and os.environ.get('DEEPSEEK_API_KEY') and os.environ.get('DEEPSEEK_MODEL'):
                from .workspace_research import research_stream
                stream = research_stream(workspace, repository, ids, question, intent_question=body.question)
            else:
                stream = comparison_stream(repository, ids, question) if len(ids) > 1 else answer_stream(repository, ids[0], question)
        except BaseException:
            question_slots.release()
            raise

        async def record():
            final = None
            error = None
            try:
                async for block in stream.body_iterator:
                    text = block.decode() if isinstance(block, bytes) else block
                    if '\nevent: final\n' in text:
                        final = json.loads(text.split('\ndata: ', 1)[1].strip())
                    if '\nevent: error\n' in text:
                        error = json.loads(text.split('\ndata: ', 1)[1].strip())
                    yield block
            finally:
                try:
                    workspace.append_message(session_id, {'question': body.question, 'answer': final,
                        'error': error, 'status': 'completed' if final else 'failed' if error else 'cancelled'})
                finally:
                    question_slots.release()
        return StreamingResponse(record(), media_type='text/event-stream', headers={'Cache-Control': 'no-cache, no-transform', 'X-Accel-Buffering': 'no'})

    return router

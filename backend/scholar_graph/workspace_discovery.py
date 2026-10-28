"""Reference acquisition plans and persistent daily/weekly tracking controls."""
from collections import Counter
from typing import Literal

from fastapi import APIRouter, Request
from pydantic import BaseModel, ConfigDict, Field

from .errors import PipelineError
from .tracking_scheduler import ScheduleConfig
from .tracking_routes import TrackingRequest


class ReferenceFetch(BaseModel):
    model_config = ConfigDict(extra='forbid')
    reference_numbers: list[int] = Field(min_length=1, max_length=100)


class TitleFetch(BaseModel):
    model_config = ConfigDict(extra='forbid')
    title: str = Field(min_length=3, max_length=500)


class ScheduleRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    enabled: bool
    frequency: Literal['daily', 'weekly']
    paper_ids: list[str] = Field(min_length=1, max_length=5)
    max_imports: int = Field(default=1, ge=0, le=5)


def reference_plan(workspace, paper_id):
    bundle = workspace.bundle(paper_id)
    counts = Counter(link['ref_id'] for link in bundle['citation_links'])
    return sorted([{'reference': ref, 'importance': counts[ref['ref_id']],
        'basis': f"该论文中有 {counts[ref['ref_id']]} 个已解析正文段落引用此文献；这是本篇内的引用频次，不是全网引用数。",
        'citation_chunks': [link['chunk_id'] for link in bundle['citation_links'] if link['ref_id'] == ref['ref_id']],
        'acquisition_ready': bool(ref['title'] or ref['arxiv_id'] or ref['doi'])} for ref in bundle['reference_entries']],
        key=lambda row: (-row['importance'], row['reference']['number']))


def discovery_routes(workspace, tasks, tracking_service):
    router = APIRouter(prefix='/api/v2')

    def fetch_task(identity, parameters, runner):
        fetcher = tasks.fetcher
        refs = parameters.get('references', [])
        items = refs if refs else [{'title_lookup': parameters['title']}]
        succeeded, failed, results = [], [], []
        for index, item in enumerate(items):
            if runner.cancelled(identity):
                break
            name = item.get('title_lookup') or item.get('title') or f"文献 [{item['number']}]"
            runner.progress(identity, index, len(items), '正在查找、下载和解析：' + name[:100])
            value = fetcher.fetch(title=item['title_lookup']) if 'title_lookup' in item else fetcher.fetch(reference=item)
            results.append({'name': name, **value})
            if value['succeeded']:
                succeeded.append({'paper_id': value['paper']['id'], 'filename': name, 'already_present': value.get('already_present', False)})
            else:
                failed.append({'filename': name, **value['error']})
            result = {'succeeded': list(succeeded), 'failed': list(failed), 'items': list(results),
                      'succeeded_count': len(succeeded), 'failed_count': len(failed),
                      'duplicate_count': sum(bool(v.get('already_present')) for v in succeeded)}
            runner.update(identity, result=result)
            runner.progress(identity, index + 1, len(items), f'已处理 {index + 1} / {len(items)} 项')
        return result if results else {'succeeded_count': 0, 'failed_count': 0}
    tasks.handlers['acquisition'] = fetch_task

    def run_tracking_task(identity, parameters, runner):
        runner.progress(identity, 0, 1, '正在按原文主题检索新论文；当前公开接口请求结束后响应停止')
        value = tracking_service.run(**parameters)
        runner.progress(identity, 1, 1, '本次论文发现已结束，真实候选、重复和失败已记录')
        return {'tracking': value, 'succeeded_count': 1 if value.get('status') in ('completed','partial') else 0,
                'failed_count': value.get('failed_count', 0)}
    tasks.handlers['tracking'] = run_tracking_task

    @router.get('/tracking/status')
    def tracking_status(request: Request):
        return {**request.app.state.workspace_tracking.status(), 'scheduler_details': request.app.state.tracking_scheduler.snapshot()}

    @router.post('/tracking/run')
    def tracking_run(body: TrackingRequest, request: Request):
        return request.app.state.workspace_tracking.run(**body.model_dump())

    @router.post('/tracking/tasks', status_code=202)
    def tracking_task(body: TrackingRequest):
        return tasks.submit('tracking', body.model_dump())

    @router.get('/papers/{paper_id}/reference-plan')
    def plan(paper_id: str):
        return reference_plan(workspace, paper_id)

    @router.post('/papers/{paper_id}/reference-tasks', status_code=202)
    def references(paper_id: str, body: ReferenceFetch):
        by_number = {row['reference']['number']: row['reference'] for row in reference_plan(workspace, paper_id)}
        if len(set(body.reference_numbers)) != len(body.reference_numbers) or any(n not in by_number for n in body.reference_numbers):
            raise PipelineError('VALIDATION_ERROR', '请选择该论文中不同的参考文献。')
        return tasks.submit('acquisition', {'references': [by_number[n] for n in body.reference_numbers]})

    @router.post('/acquisition/tasks', status_code=202)
    def title(body: TitleFetch):
        return tasks.submit('acquisition', {'title': body.title})

    @router.get('/tracking/schedule')
    def schedule(request: Request):
        config = request.app.state.tracking_scheduler.config
        return {'enabled': config.enabled, 'frequency': 'weekly' if config.interval_seconds == 604800 else 'daily',
                'paper_ids': config.paper_ids, 'max_imports': config.max_imports,
                'runtime': request.app.state.tracking_scheduler.snapshot()}

    @router.post('/tracking/schedule')
    def save_schedule(body: ScheduleRequest, request: Request):
        for pid in body.paper_ids:
            workspace.metadata(pid)
        config = ScheduleConfig(enabled=body.enabled, interval_seconds=604800 if body.frequency == 'weekly' else 86400,
                                initial_delay_seconds=15, max_imports=body.max_imports, paper_ids=tuple(body.paper_ids))
        request.app.state.tracking_scheduler.reconfigure(config)
        workspace.put('settings', 'tracking', config.__dict__, 'tracking_schedule_saved')
        return schedule(request)
    return router

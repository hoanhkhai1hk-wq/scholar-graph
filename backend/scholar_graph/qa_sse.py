"""Bounded SSE bridge; only the final event is an accepted QAAnswer."""
import asyncio
import concurrent.futures
import json
import os
import threading

from starlette.responses import StreamingResponse

from .deepseek_client import DeepSeekClient, StreamCancelled
from .errors import PipelineError
from .orchestration import EvidenceAgent


def frame(sequence, kind, value):
    return f'id: {sequence}\nevent: {kind}\ndata: {json.dumps(value, ensure_ascii=False, allow_nan=False)}\n\n'


def answer_stream(repository, paper_id, question):
    mode = os.environ.get('SCHOLAR_GRAPH_QA_MODE', 'extractive')
    if mode not in ('extractive', 'deepseek'):
        raise PipelineError('VALIDATION_ERROR', '问答模式只支持extractive或deepseek。')
    fallback = 'EXTRACTIVE_MODE' if mode == 'extractive' else (
        'MODEL_CONFIGURATION_UNAVAILABLE' if not os.environ.get('DEEPSEEK_API_KEY') or not os.environ.get('DEEPSEEK_MODEL') else None)

    async def events():
        loop = asyncio.get_running_loop()
        queue = asyncio.Queue(maxsize=32)
        stopped, active = threading.Event(), []

        def emit(kind, value):
            if stopped.is_set():
                raise StreamCancelled
            future = asyncio.run_coroutine_threadsafe(queue.put((kind, value)), loop)
            while True:
                try:
                    future.result(timeout=.1)
                    return
                except concurrent.futures.TimeoutError:
                    if stopped.is_set():
                        future.cancel()
                        raise StreamCancelled

        def worker():
            try:
                client = None if fallback else DeepSeekClient.environment()
                if client is not None:
                    active.append(client)
                value, metadata = EvidenceAgent(repository, client=client, allow_fallback=False,
                    extractive_reason=fallback).run([paper_id], question, emit=emit, stream_tokens=not fallback)
                record = value['per_paper'][0]
                repository.gate.record('QAAnswer', record)
                emit('final', record)
                emit('done', {'status': 'refused' if record['refused'] else 'completed', 'metadata': metadata,
                              'token_streaming': not bool(fallback), 'fallback_reason': fallback})
            except StreamCancelled:
                return
            except Exception as error:
                if stopped.is_set():
                    return
                envelope = error.envelope() if isinstance(error, PipelineError) else {
                    'error_code': 'INTERNAL_ERROR', 'message': '流式问答执行失败，未返回未核验答案。', 'details': None}
                try:
                    emit('error', envelope)
                    emit('done', {'status': 'error', 'token_streaming': not bool(fallback),
                                  'fallback_reason': fallback, 'model_calls': active[0].calls if active else []})
                except StreamCancelled:
                    return

        sequence = 1
        try:
            yield frame(sequence, 'mode', {'mode': 'extractive' if fallback else 'deepseek',
                'token_streaming': not bool(fallback), 'fallback_reason': fallback,
                'message': '回落模式、非 token 流式' if fallback else '真实上游token增量；增量为未校验JSON草稿，以final的QAAnswer为准。'})
            threading.Thread(target=worker, name='scholar-graph-sse', daemon=True).start()
            while True:
                try:
                    kind, value = await asyncio.wait_for(queue.get(), timeout=10)
                except asyncio.TimeoutError:
                    yield ': keep-alive\n\n'
                    continue
                sequence += 1
                yield frame(sequence, kind, value)
                if kind == 'done':
                    break
        finally:
            stopped.set()
            for client in active:
                client.cancel()

    return StreamingResponse(events(), media_type='text/event-stream',
        headers={'Cache-Control': 'no-cache, no-transform', 'X-Accel-Buffering': 'no'})

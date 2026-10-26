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
from .qa_compare import validate_comparison
from .vector_search import BgeChromaSearch


def frame(sequence, kind, value):
    return f'id: {sequence}\nevent: {kind}\ndata: {json.dumps(value, ensure_ascii=False, allow_nan=False)}\n\n'


def answer_stream(repository, paper_id, question):
    return _agent_stream(repository, [paper_id], question)


def comparison_stream(repository, paper_ids, question):
    return _agent_stream(repository, paper_ids, question, comparison=True)


def _agent_stream(repository, paper_ids, question, *, comparison=False):
    mode = os.environ.get('SCHOLAR_GRAPH_QA_MODE', 'extractive')
    if mode not in ('extractive', 'deepseek'):
        raise PipelineError('VALIDATION_ERROR', '问答模式只支持extractive或deepseek。')
    fallback = 'EXTRACTIVE_MODE' if mode == 'extractive' else (
        'MODEL_CONFIGURATION_UNAVAILABLE' if not os.environ.get('DEEPSEEK_API_KEY') or not os.environ.get('DEEPSEEK_MODEL') else None)
    agent = EvidenceAgent(repository, allow_fallback=False, extractive_reason=fallback)
    vector = agent.retriever.vector
    if comparison and not fallback and (vector is None or (isinstance(vector, BgeChromaSearch) and
            (not vector.python.is_file() or not (vector.model_path / 'config.json').is_file()))):
        fallback = 'LOCAL_VECTOR_NOT_CONFIGURED'
        agent.extractive_reason = fallback

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
                actual_fallback = fallback
                client = None if actual_fallback else DeepSeekClient.environment()
                if client is not None:
                    active.append(client)
                agent.client = client
                value, metadata = agent.run(paper_ids, question, emit=emit,
                    stream_tokens=not actual_fallback, require_vector=comparison)
                if comparison:
                    validate_comparison(value, [repository.paper(pid) for pid in paper_ids], repository.gate)
                    record = value
                else:
                    record = value['per_paper'][0]
                    repository.gate.record('QAAnswer', record)
                actual_fallback = metadata.get('fallback_reason')
                emit('final', record)
                refused = any(r['refused'] for r in value['per_paper'])
                emit('done', {'status': 'refused' if refused else 'completed', 'metadata': metadata,
                              'verified': True, 'answer_format': 'comparison' if comparison else 'QAAnswer',
                              'token_streaming': not bool(actual_fallback), 'fallback_reason': actual_fallback})
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
                'draft_verified': False, 'final_verified': True,
                'message': '回落模式、非 token 流式' if fallback else '真实上游token增量；增量为未校验JSON草稿，以通过校验的final为准。'})
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

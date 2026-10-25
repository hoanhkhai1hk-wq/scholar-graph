"""Transport inputs for module two; no changes to frozen record schemas."""

from typing import Annotated
import json
import os
from urllib.parse import quote
from fastapi import APIRouter, Response
from starlette.concurrency import run_in_threadpool
from starlette.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from .qa import QuestionAnswerer
from .qa_model import selector_from_environment
from .qa_compare import compare_papers
from .errors import PipelineError
from .deepseek_client import DeepSeekClient
from .grounded_model import GroundedModelAnswerer
from .orchestration import EvidenceAgent
from .qa_sse import answer_stream

Question = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000, strict=True)]


class QuestionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    question: Question


class CompareRequest(QuestionRequest):
    paper_ids: list[Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]*$", strict=True)]] = Field(min_length=2, max_length=10)


def question_routes(repository):
    router = APIRouter(prefix="/api/v1")

    @router.post('/papers/{paper_id}/qa/stream', response_class=StreamingResponse,
                 responses={200: {'content': {'text/event-stream': {'schema': {'type': 'string'}}}}})
    async def stream(paper_id: str, body: QuestionRequest):
        # Missing resources/bad input keep the normal HTTP error contract before SSE headers.
        await run_in_threadpool(repository.paper, paper_id)
        return answer_stream(repository, paper_id, body.question)

    @router.post("/papers/{paper_id}/qa")
    def answer(paper_id: str, body: QuestionRequest, response: Response, agent: bool = False):
        bundle = repository.paper(paper_id)
        if agent:
            value, metadata = EvidenceAgent(repository).run([paper_id], body.question)
            response.headers['X-ScholarGraph-Agent-Meta'] = quote(json.dumps(metadata, ensure_ascii=False), safe='')
            return value['per_paper'][0]
        if os.environ.get('SCHOLAR_GRAPH_QA_MODE', 'extractive') == 'deepseek':
            client = DeepSeekClient.environment()
            record, _ = GroundedModelAnswerer(repository.gate, client).answer(bundle, body.question)
            response.headers['X-ScholarGraph-QA-Meta'] = quote(json.dumps({'model_calls': client.calls}, ensure_ascii=False), safe='')
            return record
        service = QuestionAnswerer(repository.gate, selector_from_environment())
        record, _ = service.answer(bundle, body.question)
        return record

    @router.post("/compare")
    def compare(body: CompareRequest, response: Response, agent: bool = False):
        if len(set(body.paper_ids)) != len(body.paper_ids):
            raise PipelineError("VALIDATION_ERROR", "跨篇比较不接受重复论文。")
        # Resolve all inputs before any model call: a missing paper cannot produce partial results.
        bundles = [repository.paper(paper_id) for paper_id in body.paper_ids]
        if agent:
            value, metadata = EvidenceAgent(repository).run(body.paper_ids, body.question)
            response.headers['X-ScholarGraph-Agent-Meta'] = quote(json.dumps(metadata, ensure_ascii=False), safe='')
            return value
        if os.environ.get('SCHOLAR_GRAPH_QA_MODE', 'extractive') == 'deepseek':
            client = DeepSeekClient.environment()
            value, metadata = EvidenceAgent(repository, client=client, allow_fallback=False).run(body.paper_ids, body.question)
            response.headers['X-ScholarGraph-QA-Meta'] = quote(json.dumps({'model_calls': client.calls}, ensure_ascii=False), safe='')
            response.headers['X-ScholarGraph-Agent-Meta'] = quote(json.dumps(metadata, ensure_ascii=False), safe='')
            return value
        service = QuestionAnswerer(repository.gate, selector_from_environment())
        return compare_papers(bundles, body.question, service)

    return router

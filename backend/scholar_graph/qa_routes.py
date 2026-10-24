"""Transport inputs for module two; no changes to frozen record schemas."""

from typing import Annotated
from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from .qa import QuestionAnswerer
from .qa_model import selector_from_environment
from .qa_compare import compare_papers
from .errors import PipelineError

Question = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000, strict=True)]


class QuestionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    question: Question


class CompareRequest(QuestionRequest):
    paper_ids: list[Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]*$", strict=True)]] = Field(min_length=2, max_length=10)


def question_routes(repository):
    router = APIRouter(prefix="/api/v1")

    @router.post("/papers/{paper_id}/qa")
    def answer(paper_id: str, body: QuestionRequest):
        bundle = repository.paper(paper_id)
        service = QuestionAnswerer(repository.gate, selector_from_environment())
        record, _ = service.answer(bundle, body.question)
        return record

    @router.post("/compare")
    def compare(body: CompareRequest):
        if len(set(body.paper_ids)) != len(body.paper_ids):
            raise PipelineError("VALIDATION_ERROR", "跨篇比较不接受重复论文。")
        # Resolve all inputs before any model call: a missing paper cannot produce partial results.
        bundles = [repository.paper(paper_id) for paper_id in body.paper_ids]
        service = QuestionAnswerer(repository.gate, selector_from_environment())
        return compare_papers(bundles, body.question, service)

    return router

"""Transport inputs for module two; no changes to frozen record schemas."""

from typing import Annotated
from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from .qa import QuestionAnswerer
from .qa_model import selector_from_environment

Question = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000, strict=True)]


class QuestionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    question: Question


def question_routes(repository):
    router = APIRouter(prefix="/api/v1")

    @router.post("/papers/{paper_id}/qa")
    def answer(paper_id: str, body: QuestionRequest):
        bundle = repository.paper(paper_id)
        service = QuestionAnswerer(repository.gate, selector_from_environment())
        record, _ = service.answer(bundle, body.question)
        return record

    return router

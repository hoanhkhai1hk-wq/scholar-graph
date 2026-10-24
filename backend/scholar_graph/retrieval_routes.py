"""Module-four transport envelopes; frozen business records stay intact."""

from fastapi import APIRouter, Request, Response
from pydantic import ConfigDict, Field

from .api_transport import paginate
from .qa_routes import QuestionRequest

SEARCH_HEADERS = ["X-ScholarGraph-Search-Mode", "X-ScholarGraph-Vector-Status", "X-ScholarGraph-Search-Reason"]


class SearchRequest(QuestionRequest):
    model_config = ConfigDict(extra="forbid")
    paper_ids: list[str] | None = Field(None, min_length=1, max_length=100)
    page: int = Field(1, ge=1, strict=True)
    page_size: int = Field(20, ge=1, strict=True)
    min_relevance: float = Field(0, ge=0, le=1, allow_inf_nan=False)


def retrieval_routes():
    router = APIRouter(prefix="/api/v1")

    @router.post("/retrieval/search")
    def search(body: SearchRequest, request: Request, response: Response):
        items, info = request.app.state.search.search(body.question, body.paper_ids, body.min_relevance)
        result = paginate(items, body.page, body.page_size)
        reason = "PAGE_OUT_OF_RANGE" if items and not result["items"] else info["reason"]
        for header, value in zip(SEARCH_HEADERS, [info["method"], info["vector_status"], reason], strict=True):
            response.headers[header] = value
        return result

    return router

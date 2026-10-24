"""Module-four transport envelopes; frozen business records stay intact."""

from datetime import datetime, timezone
from fastapi import APIRouter, Query, Request, Response
from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator
from typing import Annotated

from .api_transport import paginate
from .qa_routes import QuestionRequest
from .recommendations import recommendations

SEARCH_HEADERS = ["X-ScholarGraph-Search-Mode", "X-ScholarGraph-Vector-Status", "X-ScholarGraph-Search-Reason"]


class SearchRequest(QuestionRequest):
    model_config = ConfigDict(extra="forbid")
    paper_ids: list[str] | None = Field(None, min_length=1, max_length=100)
    page: int = Field(1, ge=1, strict=True)
    page_size: int = Field(20, ge=1, strict=True)
    min_relevance: float = Field(0, ge=0, le=1, allow_inf_nan=False)


class FetchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500, strict=True)] | None = None
    reference: dict | None = None

    @model_validator(mode="after")
    def one_lookup(self):
        if (self.title is None) == (self.reference is None):
            raise ValueError("exactly one lookup is required")
        return self


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

    @router.post("/retrieval/fetch")
    def fetch(body: FetchRequest, request: Request):
        return request.app.state.arxiv_fetcher.fetch(body.title, body.reference)

    @router.get("/recommendations")
    def recommend(request: Request, response: Response, paper_id: str = Query(..., min_length=1),
                  as_of_year: int | None = Query(None, ge=1, le=9999),
                  page: int = Query(1, ge=1), page_size: int = Query(20, ge=1)):
        year = as_of_year if as_of_year is not None else datetime.now(timezone.utc).year
        items = recommendations(request.app.state.repository, paper_id, year)
        result = paginate(items, page, page_size)
        response.headers["X-ScholarGraph-Recommendation-Reason"] = (
            "NO_CANDIDATES" if not items else "PAGE_OUT_OF_RANGE" if not result["items"] else "OK")
        return result

    return router

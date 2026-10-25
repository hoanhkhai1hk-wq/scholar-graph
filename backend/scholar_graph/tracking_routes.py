"""Tracking, citation maintenance and local feedback transport envelopes."""

from datetime import datetime, timezone

from fastapi import APIRouter, Query, Request
from pydantic import BaseModel, ConfigDict, Field
from typing import Literal

from .citation_cleanup import clean_citations
from .recommendation_feedback import feedback, FEEDBACK_FORMULA
from .tracking_state import TrackingState


class TrackingRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    paper_ids: list[str] | None = Field(None, min_length=1, max_length=5)
    max_candidates: int = Field(5, ge=1, le=20, strict=True)
    max_imports: int = Field(2, ge=0, le=5, strict=True)
    interval_seconds: int = Field(86400, ge=60, le=2592000, strict=True)
    force: bool = Field(True, strict=True)


class FeedbackRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    paper_id: str = Field(min_length=1, max_length=200)
    seed_paper_id: str = Field(min_length=1, max_length=200)
    vote: Literal["like", "dislike"]
    profile_id: str = Field("local", pattern=r"^[A-Za-z0-9._-]{1,64}$")
    as_of_year: int | None = Field(None, ge=1, le=9999, strict=True)


def tracking_routes():
    router = APIRouter(prefix="/api/v1")

    @router.post("/retrieval/tracking/run")
    def trigger(body: TrackingRequest, request: Request):
        return request.app.state.tracking.run(**body.model_dump())

    @router.get("/retrieval/tracking/status")
    def status(request: Request):
        return request.app.state.tracking.status()

    @router.post("/retrieval/citations/cleanup")
    def cleanup(request: Request):
        with request.app.state.uploads.lock:
            return clean_citations(request.app.state.repository)

    @router.post("/recommendations/feedback")
    def vote(body: FeedbackRequest, request: Request):
        year = body.as_of_year or datetime.now(timezone.utc).year
        return feedback(request.app.state.repository, body.profile_id, body.seed_paper_id,
                        body.paper_id, 1 if body.vote == "like" else -1, year)

    @router.get("/recommendations/feedback")
    def profile(request: Request, profile_id: str = Query("local", pattern=r"^[A-Za-z0-9._-]{1,64}$")):
        state = TrackingState(request.app.state.repository.root)
        return {"profile_id": profile_id, "votes": state.votes(profile_id), "events": state.events(profile_id),
                "formula": FEEDBACK_FORMULA}

    return router

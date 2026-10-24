"""Module-six requests; no real model or key is used."""

from fastapi import APIRouter, Request
from typing import Annotated
from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from .frameworks import generate_outline
from .retrieval import load_bundles
from .reviews import generate_review


class FrameworkRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    paper_ids: list[str] = Field(min_length=1, max_length=100)


class ReviewRequest(FrameworkRequest):
    framework: dict
    requirements: list[Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500, strict=True)]] = Field(default_factory=list, max_length=10)


def writing_routes():
    router = APIRouter(prefix="/api/v1")

    @router.post("/frameworks")
    def framework(body: FrameworkRequest, request: Request):
        repo = request.app.state.repository
        return generate_outline(load_bundles(repo, body.paper_ids), repo.gate)

    @router.post("/reviews")
    def review(body: ReviewRequest, request: Request):
        repo = request.app.state.repository
        return generate_review(load_bundles(repo, body.paper_ids), body.framework, body.requirements, repo.gate)

    return router

"""Module-six requests; no real model or key is used."""

from fastapi import APIRouter, Request
from pydantic import BaseModel, ConfigDict, Field

from .frameworks import generate_outline
from .retrieval import load_bundles


class FrameworkRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    paper_ids: list[str] = Field(min_length=1, max_length=100)


def writing_routes():
    router = APIRouter(prefix="/api/v1")

    @router.post("/frameworks")
    def framework(body: FrameworkRequest, request: Request):
        repo = request.app.state.repository
        return generate_outline(load_bundles(repo, body.paper_ids), repo.gate)

    return router

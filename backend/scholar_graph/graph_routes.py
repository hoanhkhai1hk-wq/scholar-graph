"""Only the approved graph endpoint; other modules remain unimplemented."""

from fastapi import APIRouter, Query

from .errors import PipelineError
from .graph_service import build_graph


def graph_routes(repository):
    router = APIRouter(prefix="/api/v1")

    @router.get("/graph")
    def graph(paper_ids: list[str] = Query(..., min_length=1, max_length=100)):
        if len(set(paper_ids)) != len(paper_ids):
            raise PipelineError("VALIDATION_ERROR", "图谱论文集合不接受重复 id。")
        bundles = [repository.paper(paper_id) for paper_id in paper_ids]
        return build_graph(bundles, repository.gate)

    return router

"""All nineteen approved HTTP routes; no background job queue."""

import os
from pathlib import Path

from fastapi import FastAPI, Query, Response, Request, UploadFile, File
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException
from starlette.concurrency import run_in_threadpool
from starlette.middleware.cors import CORSMiddleware

from .api_repository import ApiRepository
from .api_transport import paginate
from .api_uploads import UploadService
from .errors import PipelineError
from .validation import ContractGate
from .qa_routes import question_routes
from .graph_routes import graph_routes
from .retrieval import SearchService
from .retrieval_routes import retrieval_routes, SEARCH_HEADERS
from .vector_search import vector_from_environment
from .arxiv_fetch import ArxivFetcher
from .writing_routes import writing_routes
from .chart_routes import chart_routes

PREFIX = "/api/v1"
LOCAL_ORIGINS = ["http://localhost:3000", "http://127.0.0.1:3000"]
ERROR_STATUS = {"PAPER_NOT_FOUND": 404, "UNSUPPORTED_FILE_TYPE": 415,
                "FILE_TOO_LARGE": 413, "VALIDATION_ERROR": 422,
                "PARSE_FAILED": 422, "OCR_FAILED": 422, "UPSTREAM_ERROR": 502,
                "CSV_INVALID": 422, "CHART_VALIDATION_FAILED": 422}


def create_app(*, data_dir=None, pipeline_factory=None):
    root = Path(data_dir or os.environ.get("SCHOLAR_GRAPH_DATA_DIR") or
                Path(__file__).resolve().parents[2] / "data" / "module-one").resolve()
    gate = ContractGate()
    repository = ApiRepository(root, gate)
    app = FastAPI(title="ScholarGraph modules one, two, four, five and six", version="1.2.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=LOCAL_ORIGINS,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
        expose_headers=["Location", "Link", *SEARCH_HEADERS, "X-ScholarGraph-Recommendation-Reason",
                        "X-ScholarGraph-Dedup-Warning", "X-ScholarGraph-Dedup-Warning-Encoding"],
        allow_credentials=False,
    )
    app.state.repository = repository
    uploads = UploadService(root, gate, pipeline_factory)
    app.state.uploads = uploads
    app.state.search = SearchService(repository, vector_from_environment(root))
    app.state.arxiv_fetcher = ArxivFetcher(repository, lock=uploads.lock)

    def error_response(code, message, status):
        value = {"error_code": code, "message": message, "details": None}
        gate.error(value)
        return JSONResponse(value, status_code=status)

    @app.exception_handler(PipelineError)
    async def pipeline_error(request, error):
        gate.error(error.envelope())
        return JSONResponse(error.envelope(), status_code=ERROR_STATUS.get(error.code, 500))

    @app.exception_handler(RequestValidationError)
    async def invalid_request(request, error):
        return error_response("VALIDATION_ERROR", "请求参数不合法。", 422)

    @app.exception_handler(HTTPException)
    async def http_error(request, error):
        return error_response("PAPER_NOT_FOUND" if error.status_code == 404 else "VALIDATION_ERROR",
                              "无该资源或端点。" if error.status_code == 404 else "请求无法处理。",
                              error.status_code)

    @app.exception_handler(Exception)
    async def unexpected_error(request, error):
        response = error_response("INTERNAL_ERROR", "服务内部错误。", 500)
        # ServerErrorMiddleware sits outside user middleware. Preserve CORS on its fallback.
        origin = request.headers.get("origin")
        if origin in LOCAL_ORIGINS:
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Vary"] = "Origin"
        return response

    @app.get(PREFIX + "/papers")
    def papers(page: int = Query(1, ge=1), page_size: int = Query(20, ge=1),
               title: str | None = None, year: int | None = None, source: str | None = None):
        return paginate(repository.papers(title=title, year=year, source=source), page, page_size)

    @app.post(PREFIX + "/papers", status_code=201)
    def upload(response: Response, file: UploadFile = File(...)):
        try:
            meta = uploads.single(file, response)
            response.headers["Location"] = f'{PREFIX}/papers/{meta["id"]}'
            return meta
        finally:
            file.file.close()

    @app.post(PREFIX + "/papers/batch", openapi_extra={"requestBody": {
        "required": True, "content": {"multipart/form-data": {"schema": {
            "type": "object", "properties": {"files": {"type": "array", "items": {
                "type": "string", "format": "binary"}}}, "required": ["files"]}}}}})
    async def batch(request: Request):
        # Awaited to completion: a worker thread prevents blocking status reads, not a job queue.
        try:
            form = await request.form(max_files=float("inf"), max_fields=float("inf"))
        except Exception:
            return {"succeeded": [], "failed": [{"filename": "(request)",
                    "error_code": "VALIDATION_ERROR", "error_message": "无法读取 multipart 文件列表。"}],
                    "succeeded_count": 0, "failed_count": 1}
        try:
            return await run_in_threadpool(uploads.batch, list(form.multi_items()))
        finally:
            await form.close()

    @app.get(PREFIX + "/papers/{paper_id}")
    def paper(paper_id: str, response: Response):
        value = repository.paper(paper_id)["paper_meta"]
        response.headers["Link"] = ", ".join(
            f'<{PREFIX}/papers/{paper_id}/{name}>; rel="{name}"'
            for name in ("chunks", "references", "citation-links"))
        return value

    @app.get(PREFIX + "/papers/{paper_id}/parse-status")
    def status(paper_id: str):
        return repository.status(paper_id)

    @app.get(PREFIX + "/papers/{paper_id}/dedup-decision")
    def decision(paper_id: str):
        return repository.comparison(paper_id, kind="decision")

    @app.get(PREFIX + "/papers/{paper_id}/diff-summary")
    def diff(paper_id: str):
        return repository.comparison(paper_id, kind="diff")

    @app.get(PREFIX + "/papers/{paper_id}/chunks")
    def chunks(paper_id: str, page: int = Query(1, ge=1), page_size: int = Query(20, ge=1)):
        return repository.chunk_page(paper_id, page, page_size)

    @app.get(PREFIX + "/papers/{paper_id}/references")
    def references(paper_id: str, page: int = Query(1, ge=1), page_size: int = Query(20, ge=1)):
        return paginate(repository.paper(paper_id)["reference_entries"], page, page_size)

    @app.get(PREFIX + "/papers/{paper_id}/citation-links")
    def citations(paper_id: str, page: int = Query(1, ge=1), page_size: int = Query(20, ge=1),
                  ref_id: str | None = None, chunk_id: str | None = None):
        values = repository.paper(paper_id)["citation_links"]
        values = [item for item in values if (ref_id is None or item["ref_id"] == ref_id)
                  and (chunk_id is None or item["chunk_id"] == chunk_id)]
        return paginate(values, page, page_size)

    app.include_router(question_routes(repository))
    app.include_router(graph_routes(repository))
    app.include_router(retrieval_routes())
    app.include_router(writing_routes())
    app.include_router(chart_routes())
    return app

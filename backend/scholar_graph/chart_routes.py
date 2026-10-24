"""One CSV chart endpoint, returning the frozen seven-field ChartOutput."""

import json
from fastapi import APIRouter, File, Form, Request, UploadFile
from .charts import MAX_BYTES, generate_chart, invalid_chart


def chart_routes():
    router = APIRouter(prefix="/api/v1")

    @router.post("/charts/csv")
    def chart(request: Request, file: UploadFile = File(...), chart_type: str = Form("bar"),
              value_columns: str = Form(...), x_column: str | None = Form(None), caption: str | None = Form(None)):
        try:
            raw = file.file.read(MAX_BYTES + 1)
            try:
                columns = json.loads(value_columns)
            except (ValueError, TypeError):
                invalid_chart("value_columns必须为JSON列名数组。")
            return generate_chart(raw, chart_type, columns, x_column, caption, request.app.state.repository.gate)
        finally:
            file.file.close()

    return router

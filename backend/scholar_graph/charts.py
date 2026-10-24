"""Strict CSV provenance, bounded chart rendering, and frozen ChartOutput records."""

import base64
import csv
import hashlib
import io
import json
import math
import os
import re
import threading
from decimal import Decimal, InvalidOperation
from pathlib import Path

from .errors import PipelineError

MAX_BYTES = 1024 * 1024
NUMBER = r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?"
RENDER_LOCK = threading.Lock()


def invalid_csv(message):
    raise PipelineError("CSV_INVALID", message)


def invalid_chart(message):
    raise PipelineError("CHART_VALIDATION_FAILED", message)


def read_csv(raw):
    if not raw or len(raw) > MAX_BYTES:
        invalid_csv("CSV必须非空且不超过1MiB。")
    try:
        text = raw.decode("utf-8-sig")
        if "\0" in text:
            invalid_csv("CSV包含非法空字节。")
        rows = list(csv.reader(io.StringIO(text, newline=""), strict=True))
    except (UnicodeError, csv.Error):
        invalid_csv("CSV必须是合法UTF-8逗号分隔文本。")
    if len(rows) < 2 or len(rows) > 1001:
        invalid_csv("CSV须含表头与1–1000条数据记录。")
    headers = rows[0]
    if not 1 <= len(headers) <= 20 or len(set(headers)) != len(headers) or any(not name or name != name.strip() for name in headers):
        invalid_csv("CSV须有1–20个非空、唯一且无首尾空白的列名。")
    if any(len(row) != len(headers) for row in rows[1:]):
        invalid_csv("CSV数据记录列数不一致或包含空记录。")
    return headers, rows[1:]


def numeric_cell(cell):
    value = cell.strip()
    if not re.fullmatch(NUMBER, value):
        invalid_csv("所选数据单元格须为无单位的有限十进制数；不自动换算百分比或缺失值。")
    try:
        number = Decimal(value)
        numeric = float(number)
        if not math.isfinite(numeric) or Decimal(str(numeric)) != number:
            invalid_csv("CSV数值超限或无法无损表示，拒绝静默舍入。")
    except (InvalidOperation, ValueError, OverflowError):
        invalid_csv("CSV数值无法解析。")
    return numeric


def data_series(raw, chart_type, columns, x_column):
    headers, rows = read_csv(raw)
    if (chart_type not in {"line", "bar", "scatter", "histogram"} or not isinstance(columns, list)
            or not columns or any(not isinstance(name, str) for name in columns)
            or len(set(columns)) != len(columns) or len(columns) > 10):
        invalid_chart("图表类型或数值列选择不合法。")
    if x_column is not None and (not isinstance(x_column, str) or x_column in columns):
        invalid_chart("横轴列必须独立于数值列。")
    if chart_type == "scatter" and (x_column is None or len(columns) != 1):
        invalid_chart("散点图必须指定一个横轴列与一个数值列。")
    if chart_type == "histogram" and (x_column is not None or len(columns) != 1):
        invalid_chart("直方图只接收一个数值列，不指定横轴列。")
    names = ([x_column] if x_column is not None else []) + columns
    if any(name not in headers for name in names):
        invalid_chart("请求的图表列不存在于源CSV。")
    series, checks, cells = [], [], []
    reference = "csv-" + hashlib.sha256(raw).hexdigest()
    for name in names:
        index = headers.index(name)
        values = []
        for row_number, row in enumerate(rows, 2):
            value = numeric_cell(row[index])
            values.append(value)
            cells.append(row[index].strip())
            checks.append({"value": value, "csv_anchor": {"csv_ref": reference, "row_number": row_number,
                                                          "column_name": name}, "verified": True})
        series.append({"name": name, "values": values})
    return series, checks, cells


def caption_values(caption):
    if len(caption) > 2000 or not re.fullmatch(r"CSV values: " + NUMBER + r"(?:, " + NUMBER + r")*\.", caption):
        invalid_chart("图注仅接受受限格式 CSV values: 数值, 数值.，拒绝未核验自由文本或单位换算。")
    return [Decimal(value) for value in caption[len("CSV values: "):-1].split(", ")]


def render_png(series, chart_type, x_column):
    # Keep the Matplotlib cache on D, use no GUI/pyplot, serialize shared font caches.
    os.environ.setdefault("MPLCONFIGDIR", str(Path(__file__).resolve().parents[2] / "data" / "matplotlib-cache"))
    with RENDER_LOCK:
        from matplotlib.backends.backend_agg import FigureCanvasAgg
        from matplotlib.figure import Figure
        figure = Figure(figsize=(6.4, 4), dpi=100, layout="constrained")
        canvas = FigureCanvasAgg(figure)
        axes = figure.subplots()
        axes.set_title("CSV data")
        x = series[0]["values"] if x_column is not None else list(range(2, len(series[0]["values"]) + 2))
        ys = series[1:] if x_column is not None else series
        for index, item in enumerate(ys):
            if chart_type == "line":
                axes.plot(x, item["values"], label=item["name"], marker="o")
            elif chart_type == "bar":
                width = .8 / len(ys)
                axes.bar([value + (index - (len(ys) - 1) / 2) * width for value in x], item["values"], width=width, label=item["name"])
            elif chart_type == "scatter":
                axes.scatter(x, item["values"], label=item["name"])
            else:
                axes.hist(item["values"], bins=min(10, len(item["values"])), label=item["name"])
        axes.set_xlabel("Value" if chart_type == "histogram" else x_column or "CSV record (header = 1)")
        axes.set_ylabel("Frequency" if chart_type == "histogram" else "Value")
        axes.legend()
        output = io.BytesIO()
        canvas.print_png(output)
        figure.clear()
        return "data:image/png;base64," + base64.b64encode(output.getvalue()).decode("ascii")


def validate_chart(value, raw, chart_type, columns, x_column, gate):
    try:
        gate.record("ChartOutput", value)
        series, checks, _ = data_series(raw, chart_type, columns, x_column)
        if value["chart_type"] != chart_type or value["series"] != series or value["numeric_checks"] != checks:
            invalid_chart("图表数据或逐单元格核验结果不匹配源CSV。")
        numbers = caption_values(value["caption"])
        source = {Decimal(str(check["value"])) for check in checks if check["verified"]}
        if any(number not in source for number in numbers):
            invalid_chart("图注数字未回溯到所选源CSV单元格。")
        expected_id = chart_id(raw, chart_type, columns, x_column, value["caption"])
        if value["chart_id"] != expected_id or value["image_ref"] != render_png(series, chart_type, x_column):
            invalid_chart("图表标识或实际PNG与当前数据配置不一致。")
    except PipelineError as error:
        if error.code == "CHART_VALIDATION_FAILED":
            raise
        invalid_chart("ChartOutput未通过Schema或源数据一致性校验。")
    except Exception:
        invalid_chart("图表校验失败，未发布不合规输出。")


def chart_id(raw, chart_type, columns, x_column, caption):
    config = json.dumps([chart_type, columns, x_column, caption], ensure_ascii=False).encode("utf-8")
    return "chart-" + hashlib.sha256(raw + b"\0" + config).hexdigest()


def generate_chart(raw, chart_type, columns, x_column, caption, gate):
    series, checks, cells = data_series(raw, chart_type, columns, x_column)
    caption = caption if caption is not None else "CSV values: " + ", ".join(cells[:6]) + "."
    # Fail bad captions before doing any plotting work.
    if any(number not in {Decimal(str(check["value"])) for check in checks} for number in caption_values(caption)):
        invalid_chart("图注数字未回溯到所选源CSV单元格。")
    try:
        value = {"schema_version": "1.1.0", "chart_id": chart_id(raw, chart_type, columns, x_column, caption),
                 "chart_type": chart_type, "series": series, "image_ref": render_png(series, chart_type, x_column),
                 "caption": caption, "numeric_checks": checks}
    except Exception:
        invalid_chart("PNG图表生成失败，未发布输出。")
    validate_chart(value, raw, chart_type, columns, x_column, gate)
    return value

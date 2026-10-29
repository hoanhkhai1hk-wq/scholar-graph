"""CSV preview, source table and real line/bar/3D radar artifacts for the workbench."""
import base64
import hashlib
import io
import json
import math
from decimal import Decimal,localcontext
import os
from pathlib import Path

from fastapi import APIRouter, File, Form, UploadFile

from .charts import MAX_BYTES, read_csv, data_series, invalid_chart, RENDER_LOCK
from .charts_3d import trend_facts
from .plot_style import plot_font,COLORS


def preview(raw):
    headers, rows = read_csv(raw)
    return {'columns': headers, 'rows': rows[:12], 'total_rows': len(rows), 'csv_ref': 'csv-' + hashlib.sha256(raw).hexdigest()}


def make_chart(raw, kind, columns, label_column=None):
    headers, rows = read_csv(raw)
    if not isinstance(columns, list) or not columns or any(not isinstance(c, str) for c in columns):
        invalid_chart('请选择数值列。')
    if kind not in ('table', 'line', 'bar', 'radar3d') or label_column is not None and label_column not in headers:
        invalid_chart('请选择可用图表类型和标签列。')
    if label_column in columns:
        invalid_chart('标签列与数值列应分别选择。')
    series, checks, _ = data_series(raw, 'bar', columns, None)
    if kind == 'radar3d' and (len(columns) < 3 or len(rows) > 20 or any(v < 0 for s in series for v in s['values'])):
        invalid_chart('三维雷达图需要至少三个非负数值列，最多展示二十条记录。')
    reference = 'csv-' + hashlib.sha256(raw).hexdigest()
    labels = [row[headers.index(label_column)] for row in rows] if label_column else [str(n) for n in range(2, len(rows) + 2)]
    table = {'columns': ([label_column] if label_column else []) + columns,
             'rows': [{'row_number': n + 2, 'label': labels[n], 'values': {s['name']: s['values'][n] for s in series}} for n in range(len(rows))]}
    facts = trend_facts(series, None) if len(rows) >= 2 else []
    captions=[]
    for fact in facts:
        column=headers.index(fact['series_name']);first=rows[0][column].strip();last=rows[-1][column].strip()
        with localcontext() as context:
            context.prec=1000
            delta=Decimal(last)-Decimal(first)
        trend=fact['allowed_texts'][0][len(fact['display_name']):].replace('变化速率的绝对值','相邻记录变化幅度').replace('相邻横轴区间的变化率','相邻记录差值')
        anchors=[{'csv_ref':reference,'row_number':n,'column_name':fact['series_name']} for n in fact['row_numbers']]
        captions.append({'text':f"按CSV记录顺序，{fact['series_name']}从{first}变为{last}，净变化{delta}；{trend}",
            'series_name':fact['series_name'],'trend':fact['trend'],'shape':fact['shape'],'csv_anchors':anchors,
            'numeric_facts':{'first':{'text':first,'anchor':anchors[0]},'last':{'text':last,'anchor':anchors[-1]},
                'delta':{'value':str(delta),'operation':'last_minus_first','source_anchors':[anchors[-1],anchors[0]]}}})
    if not captions:
        captions=[{'text':'只有一条记录，无法判断上升、下降或波动趋势；请增加记录后比较。','series_name':s['name'],'trend':'insufficient_data','shape':'undetermined',
                   'csv_anchors':[{'csv_ref':reference,'row_number':2,'column_name':s['name']}]} for s in series]
    image = None
    if kind != 'table':
        os.environ.setdefault('MPLCONFIGDIR', str(Path(__file__).resolve().parents[2] / 'data/matplotlib-cache'))
        with RENDER_LOCK:
            from matplotlib.figure import Figure
            from matplotlib.backends.backend_agg import FigureCanvasAgg
            font,has_cjk = plot_font()
            fig = Figure(figsize=(9, 5.5), dpi=150, layout='constrained')
            canvas = FigureCanvasAgg(fig)
            ax = fig.add_subplot(projection='3d' if kind == 'radar3d' else None)
            if kind == 'radar3d':
                angles = [2 * math.pi * i / len(columns) for i in range(len(columns))]
                maximum = max(v for s in series for v in s['values']) or 1
                for j, label in enumerate(labels):
                    values = [s['values'][j] for s in series]
                    xs = [v * math.cos(a) for v, a in zip(values, angles)]
                    ys = [v * math.sin(a) for v, a in zip(values, angles)]
                    ax.plot(xs + xs[:1], ys + ys[:1], [j] * (len(columns) + 1), marker='o', label=label,color=COLORS[j%len(COLORS)])
                for angle, column in zip(angles, columns):
                    ax.plot([0, maximum * math.cos(angle)], [0, maximum * math.sin(angle)], [0, 0], color='#9caea3', alpha=.6)
                    ax.text(maximum * math.cos(angle), maximum * math.sin(angle), 0, column, fontproperties=font)
                ax.set_zticks(range(len(labels)), labels, fontproperties=font)
                ax.set_title('三维雷达图 · 原始值与记录顺序' if has_cjk else '3D radar: raw values by CSV record', fontproperties=font)
            else:
                xs = list(range(len(rows)))
                for index, s in enumerate(series):
                    if kind == 'line':
                        ax.plot(xs, s['values'], marker='o', label=s['name'],color=COLORS[index%len(COLORS)],linewidth=2)
                    else:
                        width = .8 / len(series)
                        ax.bar([x + (index - (len(series) - 1) / 2) * width for x in xs], s['values'], width=width, label=s['name'],color=COLORS[index%len(COLORS)])
                if len(rows) <= 30:
                    ax.set_xticks(xs, labels, rotation=25, fontproperties=font)
                ax.set_title('CSV 原始数据' if has_cjk else 'CSV source data', fontproperties=font)
                ax.grid(axis='y',alpha=.18);ax.set_axisbelow(True)
                for side in ['top','right']:ax.spines[side].set_visible(False)
            ax.legend(prop=font)
            output = io.BytesIO(); canvas.print_png(output); fig.clear()
            image = 'data:image/png;base64,' + base64.b64encode(output.getvalue()).decode('ascii')
    return {'kind': kind, 'csv_ref': reference, 'image': image, 'data_table': table, 'numeric_checks': checks,
            'captions': captions, 'caption_method': 'deterministic_trend_endpoints_and_exact_difference_from_source_cells',
            'radar_note': '各指标直接使用原始数值，未归一化；仅在量纲可比较时使用。Z 轴表示记录顺序。' if kind == 'radar3d' else None}


def chart_workspace_routes():
    router = APIRouter(prefix='/api/v2')

    @router.post('/charts/preview')
    def csv_preview(file: UploadFile = File(...)):
        try:
            return preview(file.file.read(MAX_BYTES + 1))
        finally:
            file.file.close()

    @router.post('/charts')
    def chart(file: UploadFile = File(...), kind: str = Form(...), columns: str = Form(...), label_column: str | None = Form(None)):
        try:
            try:
                selected = json.loads(columns)
            except ValueError:
                invalid_chart('列选择格式不正确。')
            return make_chart(file.file.read(MAX_BYTES + 1), kind, selected, label_column)
        finally:
            file.file.close()
    return router

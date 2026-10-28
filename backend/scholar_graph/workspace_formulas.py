"""Traceable local formula recognition kept separate from frozen parser records."""
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict, Field

from .errors import PipelineError
from .pdf_files import PdfFiles
from .workspace import now

MODEL = 'PP-FormulaNet-S'


class FormulaPatch(BaseModel):
    model_config = ConfigDict(extra='forbid')
    latex: str = Field(min_length=1,max_length=12000)
    note: str = Field(min_length=1,max_length=1000)


def formula_model():
    cache = Path(os.environ.get('SCHOLAR_GRAPH_OCR_CACHE_DIR', 'data/paddle-models'))
    root = Path(os.environ.get('SCHOLAR_GRAPH_FORMULA_MODEL_DIR', str(cache/'official_models'/MODEL)))
    if not (root/'inference.yml').is_file() or not (root/'inference.pdiparams').is_file():
        raise PipelineError('UPSTREAM_ERROR', '本地公式识别模型尚未准备完成，未生成或编造 LaTeX。')
    return root


def checked_latex(value):
    if not isinstance(value, str) or not 1 <= len(value.strip()) <= 12000:
        raise PipelineError('VALIDATION_ERROR', '公式识别结果为空或超过长度限制。')
    value = value.strip()
    if re.search(r'\\(?:input|include|write|openout|read|usepackage|documentclass|href|url|html|class|style)\b', value):
        raise PipelineError('VALIDATION_ERROR', '公式识别包含不支持的非数学指令。')
    depth = 0
    for token in re.findall(r'\\[{}]|[{}]', value):
        if token == '{': depth += 1
        elif token == '}': depth -= 1
        if depth < 0: break
    if depth != 0:
        raise PipelineError('VALIDATION_ERROR', '公式识别的括号结构不完整，请对照原图核对。')
    return value


def formula_regions(workspace, pid):
    return [{'region_id':f'p{page["page_number"]:04d}-r{i:04d}', 'page_number':page['page_number'], 'bbox':r['bbox']}
            for page in workspace.layout_pages(pid) for i,r in enumerate(page['regions']) if r['label']=='formula']


def formula_task(workspace, identity, parameters, runner):
    pid = parameters['paper_id']; meta = workspace.metadata(pid)
    model_dir = formula_model()
    regions = formula_regions(workspace, pid)
    if not regions:
        raise PipelineError('VALIDATION_ERROR', '请先识别版面区域；当前没有可核对的公式区域。')
    fingerprint = hashlib.sha256()
    with (model_dir/'inference.pdiparams').open('rb') as stream:
        while block := stream.read(1024*1024): fingerprint.update(block)
    digest = fingerprint.hexdigest()
    results, failures = [], []
    for start in range(0,len(regions),12):
        if runner.cancelled(identity): break
        selected = regions[start:start+12]
        runner.progress(identity,len(results)+len(failures),len(regions),'正在根据公式原图识别 LaTeX；识别结果需对照原文')
        parent = workspace.root/'.formula-jobs'; parent.mkdir(exist_ok=True)
        try:
            with tempfile.TemporaryDirectory(dir=parent) as directory:
                if not Path(directory).resolve().is_relative_to(workspace.root.resolve()): raise ValueError()
                manifest = Path(directory)/'regions.json'
                manifest.write_text(json.dumps(selected),encoding='utf-8')
                env = {k:v for k,v in os.environ.items() if not any(s in k.upper() for s in ('API_KEY','TOKEN','SECRET','PASSWORD'))}
                env.update(PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK='True',PYTHONIOENCODING='utf-8')
                response = subprocess.run([sys.executable,str(Path(__file__).with_name('_formula_worker.py')),
                    str(PdfFiles(workspace.root).locate(pid)),str(manifest),str(model_dir)],
                    capture_output=True,env=env,timeout=300,check=False)
            if response.returncode or len(response.stdout)>1024*1024: raise ValueError()
            rows = json.loads(response.stdout)
            if not isinstance(rows,list) or [r.get('region_id') for r in rows] != [r['region_id'] for r in selected]: raise ValueError()
            for region,row in zip(selected,rows,strict=True):
                try:
                    latex = checked_latex(row.get('latex'))
                except PipelineError as error:
                    failures.append({'filename':'第 '+str(region['page_number'])+' 页公式','error_code':error.code,'message':error.message})
                    continue
                value = {**region,'paper_id':pid,'source_file_hash':meta['file_hash'],'model':MODEL,'model_sha256':digest,
                         'latex':latex,'status':'recognized_unreviewed','recognized_at':now(),
                         'notice':'本地模型识别候选，格式校验不能证明数学语义正确；请对照原图。'}
                workspace.put('formula',pid+':'+region['region_id'],value,'formula_recognized')
                results.append(value)
        except Exception as error:
            message = error.message if isinstance(error,PipelineError) else '本地公式识别未完成，已取得的结果保留，可重试。'
            failures.extend({'filename':'第 '+str(r['page_number'])+' 页公式','error_code':'PARSE_FAILED','message':message} for r in selected)
        runner.update(identity,result={'formulas':results,'succeeded_count':len(results),'failed_count':len(failures),'failed':failures})
    runner.progress(identity,len(results)+len(failures),len(regions),'公式识别结果已保存，保留原图供核对')
    return {'formulas':results,'succeeded_count':len(results),'failed_count':len(failures),'failed':failures}


def formula_routes(workspace,tasks):
    router = APIRouter(prefix='/api/v2')
    tasks.handlers['formula'] = lambda identity,parameters,runner: formula_task(workspace,identity,parameters,runner)

    @router.post('/papers/{paper_id}/formula-tasks',status_code=202)
    def submit(paper_id:str):
        workspace.metadata(paper_id); formula_model()
        return tasks.submit('formula',{'paper_id':paper_id})

    @router.get('/papers/{paper_id}/formulas')
    def formulas(paper_id:str):
        meta = workspace.metadata(paper_id)
        rows = [r for r in workspace.all('formula') if r['paper_id']==paper_id and r['source_file_hash']==meta['file_hash']]
        for i,row in enumerate(rows):
            correction = workspace.read('formula_correction',paper_id+':'+row['region_id'])
            if correction and correction['source_file_hash']==meta['file_hash'] and correction['bbox']==row['bbox']:
                rows[i] = {**row,'recognized_latex':row['latex'],'latex':correction['latex'],
                           'status':'corrected_from_source','correction':correction,
                           'notice':'已保存原图核对后的人工修正；机器候选和修正说明分别保留。'}
        try: formula_model(); ready = True
        except PipelineError: ready = False
        return {'items':sorted(rows,key=lambda r:r['region_id']), 'expected_regions':len(formula_regions(workspace,paper_id)),
                'model_ready':ready,'notice':'识别候选始终保留对应原图；尚未逐式核对时不能认定数学表达完全正确。'}

    @router.patch('/papers/{paper_id}/formulas/{region_id}')
    def correct(paper_id:str,region_id:str,body:FormulaPatch):
        meta = workspace.metadata(paper_id)
        row = workspace.read('formula',paper_id+':'+region_id)
        if not row or row['source_file_hash']!=meta['file_hash']:
            raise PipelineError('PAPER_NOT_FOUND','没有可修正的当前论文公式识别结果。')
        if not body.note.strip():
            raise PipelineError('VALIDATION_ERROR','请填写原图核对与修正说明。')
        value = {'paper_id':paper_id,'region_id':region_id,'source_file_hash':meta['file_hash'],
                 'bbox':row['bbox'],'latex':checked_latex(body.latex),'original_latex':row['latex'],
                 'note':body.note.strip(),'source':'user_formula_correction','updated_at':now()}
        return workspace.put('formula_correction',paper_id+':'+region_id,value,'formula_corrected')
    return router

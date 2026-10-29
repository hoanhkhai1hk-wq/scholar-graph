"""Durable uploads and task operations; a request owns only its input snapshot."""
from pathlib import Path
import uuid

from fastapi import APIRouter, Request
from starlette.datastructures import UploadFile
from pydantic import BaseModel

from .api_uploads import MAX_BYTES
from .errors import PipelineError
from .tracking_state import operation_lock


def task_routes(workspace, tasks, uploads):
    router = APIRouter(prefix='/api/v2')

    def upload_task(identity, parameters, runner):
        succeeded, failed = [], []
        total = len(parameters['files'])
        for index, item in enumerate(parameters['files']):
            if runner.cancelled(identity):
                break
            runner.progress(identity, index, total, '正在解析 ' + item['filename'] + '；可取消，已完成页面将保留')
            try:
                if item.get('error'):
                    raise PipelineError(item['error']['error_code'], item['error']['message'])
                path = workspace.root / '.task-inputs' / item['storage']
                allowed = (workspace.root / '.task-inputs').resolve()
                if path.is_symlink() or not path.resolve().is_relative_to(allowed):
                    raise PipelineError('VALIDATION_ERROR', '任务输入路径不合法。')
                with path.open('rb') as stream, uploads.lock, operation_lock(workspace.root, 'ingestion', timeout=30):
                    meta, initial, warning, dedup, parse_metadata = uploads._one(UploadFile(filename=item['filename'], file=stream),
                        cancelled=lambda: runner.cancelled(identity), on_page_progress=lambda completed, count:
                            runner.progress(identity, index, total, f'{item["filename"]}：已解析 {completed} / {count} 页；检查点已保存'))
                state = workspace.read('paper', meta['id'], {})
                state.setdefault('filename', item['filename'])
                if parse_metadata and parse_metadata.get('author_profiles'):
                    state['author_profiles'] = parse_metadata['author_profiles']
                workspace.put('paper', meta['id'], state)
                from .front_matter import apply_local_front_matter
                apply_local_front_matter(workspace, meta['id'])
                succeeded.append({'paper_id': meta['id'], 'filename': item['filename'], 'warning': warning, 'dedup': dedup})
            except Exception as error:
                envelope = error.envelope() if isinstance(error, PipelineError) else {'error_code': 'INTERNAL_ERROR', 'message': '该文件解析失败。', 'details': None}
                failed.append({'filename': item['filename'], **envelope})
            runner.progress(identity, index + 1, total, '已处理 ' + str(index + 1) + ' / ' + str(total) + ' 个文件')
        return {'succeeded': succeeded, 'failed': failed, 'succeeded_count': len(succeeded), 'failed_count': len(failed)}
    tasks.handlers['upload'] = upload_task

    @router.post('/uploads', status_code=202)
    async def submit_upload(request: Request):
        form = await request.form(max_files=20, max_fields=10)
        files = form.getlist('files')
        if not files or len(files) > 20 or any(not hasattr(f, 'read') for f in files):
            await form.close()
            raise PipelineError('VALIDATION_ERROR', '请选择 1–20 个文件。')
        declared = form.get('file_count')
        if declared is not None and declared!=str(len(files)):
            await form.close()
            raise PipelineError('VALIDATION_ERROR','接收的文件数与所选数量不一致，未开始解析，请重新上传。')
        folder = workspace.root / '.task-inputs' / uuid.uuid4().hex
        folder.mkdir(parents=True)
        parameters = {'files': []}
        try:
            for index, upload in enumerate(files):
                name = (upload.filename or 'unnamed.pdf')[:200]
                item = {'filename': name, 'storage': f'{folder.name}/{index}.bin'}
                if Path(name).suffix.lower() != '.pdf':
                    item['error'] = {'error_code': 'UNSUPPORTED_FILE_TYPE', 'message': '仅支持 PDF 文件。'}
                else:
                    size = 0
                    with (folder / f'{index}.bin').open('xb') as output:
                        while block := await upload.read(1024 * 1024):
                            size += len(block)
                            if size > MAX_BYTES:
                                item['error'] = {'error_code': 'FILE_TOO_LARGE', 'message': 'PDF 超过 50 MiB 限制。'}
                                break
                            output.write(block)
                parameters['files'].append(item)
            return tasks.submit('upload', parameters)
        finally:
            await form.close()

    @router.get('/tasks')
    def list_tasks():
        values = workspace.all('task')
        keys = {'id', 'kind', 'status', 'created_at', 'started_at', 'finished_at', 'progress', 'error'}
        return sorted([{k: v for k, v in task.items() if k in keys} for task in values], key=lambda t: t['created_at'], reverse=True)[:50]

    @router.get('/tasks/{task_id}')
    def task(task_id: str):
        return tasks.get(task_id)

    @router.post('/tasks/{task_id}/cancel')
    def cancel(task_id: str):
        return tasks.cancel(task_id)

    @router.post('/tasks/{task_id}/retry', status_code=202)
    def retry(task_id: str):
        return tasks.retry(task_id)

    return router

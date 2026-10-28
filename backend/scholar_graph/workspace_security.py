"""Optional internal service boundary for the access-code protected public demo."""
from collections import deque
import hmac
import json
import os
import threading
import time

from fastapi.responses import JSONResponse


def install_service_boundary(app, root):
    token = os.environ.get('SG_SERVICE_TOKEN')
    demo = os.environ.get('SG_DEMO_MODE') == 'true'
    if demo and (not token or len(token) < 32 or os.environ.get('SG_DATA_CLASS') != 'public_demo' or root.name == 'module-one'):
        raise ValueError('Public demo requires a dedicated public_demo data root and internal service token.')
    if demo:
        try:
            manifest = json.loads((root / 'demo-manifest.json').read_text(encoding='utf-8'))
            if manifest.get('data_class') != 'public_demo' or manifest.get('personal_sessions_copied') is not False or manifest.get('personal_tasks_copied') is not False:
                raise ValueError()
            storage_limit = int(os.environ.get('SG_DEMO_STORAGE_LIMIT_BYTES', str(2*1024**3)))
            if storage_limit <= 0: raise ValueError()
        except (OSError, ValueError):
            raise ValueError('Public demo requires a verified isolation manifest and positive storage limit.') from None
    active = deque()
    guard = threading.Lock()

    @app.middleware('http')
    async def service_boundary(request, call_next):
        if token and request.url.path.startswith('/api/'):
            received = request.headers.get('x-scholargraph-service', '')
            if not hmac.compare_digest(received, token):
                return JSONResponse({'error_code': 'AUTH_REQUIRED', 'message': '请通过工作台评审入口访问。', 'details': None}, status_code=401)
        if demo:
            length = request.headers.get('content-length')
            if length and (not length.isdigit() or int(length) > 100 * 1024 * 1024):
                return JSONResponse({'error_code': 'FILE_TOO_LARGE', 'message': '请求超过公开体验资源限制。', 'details': None}, status_code=413)
            if request.method == 'POST' and request.url.path.endswith(('/uploads', '/papers', '/papers/batch', '/acquisition/tasks', '/reference-tasks')):
                stored = 0
                for path in root.rglob('*'):
                    try:
                        if path.is_file() and not path.is_symlink():
                            stored += path.stat().st_size
                    except FileNotFoundError:
                        # Atomic task writes can remove a temporary file during this scan.
                        continue
                if stored + max(100*1024*1024, int(length or 0)) > storage_limit:
                    return JSONResponse({'error_code': 'STORAGE_LIMIT', 'message': '演示库已达到存储资源限额，原有论文与历史保留。', 'details': None}, status_code=413)
            if request.method == 'POST':
                with guard:
                    now = time.monotonic()
                    while active and now - active[0] > 60:
                        active.popleft()
                    if len(active) >= 20:
                        return JSONResponse({'error_code': 'RATE_LIMITED', 'message': '体验请求较多，请一分钟后重试。', 'details': None}, status_code=429)
                    active.append(now)
        return await call_next(request)

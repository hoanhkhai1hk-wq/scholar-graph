"""In-memory DeepSeek chat/tool protocol. Only an explicit metadata allowlist survives."""
import json
import os
import re
import time
import threading
from urllib.parse import urlparse

import httpx

from .errors import PipelineError


class StreamCancelled(Exception):
    """Local disconnect signal; never serialized as an upstream failure."""


class DeepSeekClient:
    def __init__(self, *, key, model, base_url='https://api.deepseek.com', transport=None, timeout=60):
        url = urlparse(base_url)
        if not key or not model:
            raise PipelineError('UPSTREAM_ERROR', 'DeepSeek环境变量未设置，未调用模型。')
        if (not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._/-]{0,127}', model) or key in model or model.startswith(('sk-', 'hf_', 'ghp_'))
                or url.scheme != 'https' or url.hostname != 'api.deepseek.com' or url.port not in (None, 443)
                or url.username or url.password or url.query or url.fragment or url.path.rstrip('/') not in ('', '/v1')):
            raise PipelineError('VALIDATION_ERROR', 'DeepSeek配置不合法。')
        self._key, self.model, self.base_url = key, model, base_url.rstrip('/')
        self.transport, self.timeout = transport, timeout
        self.calls = []
        self._stopped = threading.Event()
        self._response = None

    def cancel(self):
        self._stopped.set()
        response = self._response
        if response is not None:
            try:
                response.close()
            except Exception:
                pass  # Disconnect cleanup only; not suppression of an answer error.

    def stream_complete(self, messages, *, phase, on_delta, tools=None, tool_choice='none', max_tokens=2400):
        """Forward real content deltas; retain only assembled JSON in memory for validation."""
        started = time.perf_counter()
        meta = {'provider': 'deepseek', 'model': self.model, 'phase': phase,
                'elapsed_seconds': None, 'prompt_tokens': None, 'completion_tokens': None,
                'total_tokens': None, 'http_status': None, 'status': 'failed'}
        content, finished, done, size = [], False, False, 0
        try:
            body = {'model': self.model, 'messages': messages, 'temperature': 0, 'max_tokens': max_tokens,
                    'thinking': {'type': 'disabled'}, 'stream': True, 'stream_options': {'include_usage': True},
                    'response_format': {'type': 'json_object'}}
            if tools:
                body.update(tools=tools, tool_choice=tool_choice)
            with httpx.Client(timeout=httpx.Timeout(self.timeout, connect=10), follow_redirects=False,
                              trust_env=False, transport=self.transport) as client:
                with client.stream('POST', self.base_url + '/chat/completions', json=body,
                                   headers={'Authorization': 'Bearer ' + self._key}) as response:
                    self._response = response
                    meta['http_status'] = response.status_code
                    if response.status_code != 200:
                        raise PipelineError('UPSTREAM_ERROR', f'DeepSeek上游返回HTTP {response.status_code}，未生成答案。')
                    if not response.headers.get('content-type', '').lower().startswith('text/event-stream'):
                        raise ValueError
                    for line in response.iter_lines():
                        if self._stopped.is_set():
                            raise StreamCancelled
                        if time.perf_counter() - started > self.timeout:
                            raise ValueError
                        size += len(line.encode('utf-8'))
                        if size > 2 * 1024 * 1024:
                            raise ValueError
                        if not line or line.startswith(':'):
                            continue
                        if not line.startswith('data:'):
                            raise ValueError
                        data = line[5:].strip()
                        if data == '[DONE]':
                            done = True
                            break
                        payload = json.loads(data)
                        if 'error' in payload:
                            raise ValueError
                        choices = payload.get('choices', [])
                        if not isinstance(choices, list) or len(choices) > 1:
                            raise ValueError
                        if choices:
                            choice = choices[0]
                            if choice.get('index', 0) != 0:
                                raise ValueError
                            delta = choice.get('delta', {})
                            if not isinstance(delta, dict) or delta.get('tool_calls'):
                                raise ValueError
                            text = delta.get('content')
                            if text is not None:
                                if not isinstance(text, str) or (finished and text):
                                    raise ValueError
                                if text:
                                    content.append(text)
                                    on_delta(text)
                            reason = choice.get('finish_reason')
                            if reason is not None:
                                if reason != 'stop':
                                    raise ValueError
                                finished = True
                        usage = payload.get('usage')
                        if isinstance(usage, dict):
                            for name in ('prompt_tokens', 'completion_tokens', 'total_tokens'):
                                n = usage.get(name)
                                meta[name] = n if type(n) is int and n >= 0 else None
            if not done or not finished or not content:
                raise ValueError
            meta['status'] = 'succeeded'
            return {'role': 'assistant', 'content': ''.join(content)}
        except StreamCancelled:
            meta['status'] = 'cancelled'
            raise
        except PipelineError:
            raise
        except Exception:
            if self._stopped.is_set():
                meta['status'] = 'cancelled'
                raise StreamCancelled from None
            raise PipelineError('UPSTREAM_ERROR', 'DeepSeek流式连接、超时或返回格式错误，未返回未核验答案。') from None
        finally:
            self._response = None
            meta['elapsed_seconds'] = round(time.perf_counter() - started, 6)
            self.calls.append(meta)

    def __repr__(self):
        return '<DeepSeekClient credentials=redacted>'

    @classmethod
    def environment(cls):
        return cls(key=os.environ.get('DEEPSEEK_API_KEY', ''), model=os.environ.get('DEEPSEEK_MODEL', ''),
                   base_url=os.environ.get('DEEPSEEK_BASE_URL', 'https://api.deepseek.com'))

    def complete(self, messages, *, phase, tools=None, tool_choice='auto', json_mode=True, max_tokens=2400):
        started = time.perf_counter()
        meta = {'provider': 'deepseek', 'model': self.model, 'phase': phase,
                'elapsed_seconds': None, 'prompt_tokens': None, 'completion_tokens': None,
                'total_tokens': None, 'http_status': None, 'status': 'failed'}
        try:
            body = {'model': self.model, 'messages': messages, 'temperature': 0, 'max_tokens': max_tokens,
                    'thinking': {'type': 'disabled'}, 'stream': False}
            if tools:
                body.update(tools=tools, tool_choice=tool_choice)
            if json_mode:
                body['response_format'] = {'type': 'json_object'}
            with httpx.Client(timeout=httpx.Timeout(self.timeout, connect=10), follow_redirects=False,
                              trust_env=False, transport=self.transport) as client:
                response = client.post(self.base_url + '/chat/completions', json=body,
                                       headers={'Authorization': 'Bearer ' + self._key})
                meta['http_status'] = response.status_code
                meta['response_bytes'] = len(response.content)
                if response.status_code != 200:
                    raise PipelineError('UPSTREAM_ERROR', f'DeepSeek上游返回HTTP {response.status_code}，未生成答案。')
                if len(response.content) > 2 * 1024 * 1024:
                    raise ValueError
                payload = response.json()
            choice = payload['choices'][0]
            meta['finish_reason'] = choice.get('finish_reason') if choice.get('finish_reason') in ('stop','tool_calls','length','content_filter','insufficient_system_resource') else 'unknown'
            if choice.get('finish_reason') not in ('stop', 'tool_calls'):
                raise ValueError
            raw = choice['message']
            message = {'role': 'assistant', 'content': raw.get('content') or ''}
            if raw.get('tool_calls'):
                if not isinstance(raw['tool_calls'], list) or len(raw['tool_calls']) > 8:
                    raise ValueError
                message['tool_calls'] = []
                ids = set()
                for call in raw['tool_calls']:
                    if (call.get('type') != 'function' or not isinstance(call.get('id'), str)
                            or not re.fullmatch(r'[A-Za-z0-9_-]{1,128}', call['id']) or call['id'] in ids):
                        raise ValueError
                    ids.add(call['id'])
                    f = call['function']
                    if not isinstance(f.get('name'), str) or not isinstance(f.get('arguments'), str) or len(f['arguments']) > 8192:
                        raise ValueError
                    message['tool_calls'].append({'id': call['id'], 'type': 'function',
                                                  'function': {'name': f['name'], 'arguments': f['arguments']}})
            if not isinstance(message['content'], str):
                raise ValueError
            for name in ('prompt_tokens', 'completion_tokens', 'total_tokens'):
                v = payload.get('usage', {}).get(name)
                meta[name] = v if type(v) is int and v >= 0 else None
            meta['status'] = 'succeeded'
            return message
        except PipelineError:
            raise
        except Exception as error:
            meta['failure_kind'] = type(error).__name__
            raise PipelineError('UPSTREAM_ERROR', 'DeepSeek连接、超时或返回格式错误，未生成未核验答案。') from None
        finally:
            meta['elapsed_seconds'] = round(time.perf_counter() - started, 6)
            self.calls.append(meta)
            # Never retain headers, request/response objects, raw messages or reasoning content.


def json_content(message):
    try:
        value = json.loads(message['content'])
        if not isinstance(value, dict):
            raise ValueError
        return value
    except Exception:
        raise PipelineError('VALIDATION_ERROR', '模型未返回要求的结构化答案。') from None

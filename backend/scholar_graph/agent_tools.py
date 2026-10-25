"""Strict function definitions and dispatch to real local services, never HTTP impersonation."""
import json
import time

from jsonschema import Draft202012Validator

from .errors import PipelineError
from .graph_service import build_graph
from .grounded_model import evidence_candidates

PAPER_IDS = {'type': 'array', 'minItems': 1, 'maxItems': 10, 'uniqueItems': True,
             'items': {'type': 'string', 'pattern': '^[A-Za-z0-9][A-Za-z0-9._:-]*$'}}
FUNCTIONS = [
    {'type': 'function', 'function': {'name': 'search',
     'description': 'Search actual saved Chunk evidence within the supplied paper collection. Use a focused query for each paper. No invented evidence.',
     'parameters': {'type': 'object', 'properties': {'paper_ids': PAPER_IDS,
         'query': {'type': 'string', 'minLength': 1, 'maxLength': 300},
         'limit': {'type': 'integer', 'minimum': 1, 'maximum': 24}},
         'required': ['paper_ids', 'query', 'limit'], 'additionalProperties': False}}},
    {'type': 'function', 'function': {'name': 'graph_query',
     'description': 'Read the local citation graph. Missing citation edges are not proof of no intellectual relationship.',
     'parameters': {'type': 'object', 'properties': {'paper_ids': PAPER_IDS},
                    'required': ['paper_ids'], 'additionalProperties': False}}},
    {'type': 'function', 'function': {'name': 'arxiv_fetch',
     'description': 'Fetch a paper by exact title through the public arXiv API and the existing parser. Only allowed when the user explicitly requests acquisition.',
     'parameters': {'type': 'object', 'properties': {'title': {'type': 'string', 'minLength': 1, 'maxLength': 300}},
                    'required': ['title'], 'additionalProperties': False}}},
]


class AgentTools:
    def __init__(self, repository, paper_ids, *, fetcher=None, allow_fetch=False):
        self.repository, self.paper_ids = repository, set(paper_ids)
        self.fetcher, self.allow_fetch = fetcher, allow_fetch
        self.trace = []

    def execute(self, call, *, attempt):
        started = time.perf_counter()
        name = call.get('function', {}).get('name')
        row = {'tool_name': name if name in {'search', 'graph_query', 'arxiv_fetch'} else 'unknown',
               'tool_call_id': call.get('id'), 'attempt': attempt, 'origin': 'model_function_call',
               'arguments_summary': {}, 'return_summary': {}, 'elapsed_seconds': None, 'status': 'failed'}
        try:
            definition = next((x['function'] for x in FUNCTIONS if x['function']['name'] == name), None)
            if definition is None:
                raise PipelineError('VALIDATION_ERROR', '模型请求了未定义工具。')
            try:
                args = json.loads(call['function']['arguments'])
                Draft202012Validator(definition['parameters']).validate(args)
            except Exception:
                raise PipelineError('VALIDATION_ERROR', '工具参数未通过严格Schema校验。') from None
            if name in ('search', 'graph_query'):
                if not set(args['paper_ids']).issubset(self.paper_ids):
                    raise PipelineError('VALIDATION_ERROR', '工具访问超出用户论文集合。')
                row['arguments_summary']['paper_ids'] = args['paper_ids']
            if name == 'search':
                row['arguments_summary'].update(query_chars=len(args['query']), limit=args['limit'])
                items = []
                for pid in args['paper_ids']:
                    items.extend(evidence_candidates(self.repository.paper(pid), args['query'], limit=args['limit']))
                result = {'items': items, 'reason': 'OK' if items else 'NO_MATCHING_CHUNKS', 'method': 'lexical'}
                row['return_summary'] = {'evidence_count': len(items), 'method': 'lexical'}
            elif name == 'graph_query':
                graph = build_graph([self.repository.paper(pid) for pid in args['paper_ids']], self.repository.gate)
                result = {key: graph[key] for key in ('nodes', 'edges', 'layers')}
                row['return_summary'] = {'nodes': len(graph['nodes']), 'edges': len(graph['edges'])}
            else:
                row['arguments_summary'] = {'title_chars': len(args['title'])}
                if not self.allow_fetch or self.fetcher is None:
                    raise PipelineError('VALIDATION_ERROR', '本任务未授权新增抓取论文。')
                operation = self.fetcher.fetch(title=args['title'])
                result = {key: operation[key] for key in ('succeeded', 'paper', 'parse_status', 'error')}
                if operation['succeeded']:
                    self.paper_ids.add(operation['paper']['id'])
                row['return_summary'] = {'succeeded': operation['succeeded'],
                                         'error_code': operation['error']['error_code'] if operation['error'] else None}
            row['status'] = 'succeeded'
            return result
        except PipelineError as error:
            row['return_summary'] = {'error_code': error.code}
            return {'error': error.envelope()}
        except Exception:
            row['return_summary'] = {'error_code': 'INTERNAL_ERROR'}
            return {'error': {'error_code': 'INTERNAL_ERROR', 'message': '工具执行失败，未编造结果。', 'details': None}}
        finally:
            row['elapsed_seconds'] = round(time.perf_counter() - started, 6)
            self.trace.append(row)

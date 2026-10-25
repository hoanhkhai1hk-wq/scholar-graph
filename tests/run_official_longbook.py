"""官方 pdf/ 真文件：完整长书上传，不改页数上限、不拆分。"""
import json
import sys
from official_pdf_support import ROOT, prepare, header, save, file_info, upload, parsed_details, read
sys.path.insert(0, str(ROOT / 'backend'))
from fastapi.testclient import TestClient
from scholar_graph.api import create_app


def main():
    root = prepare(ROOT / 'data/official-pdf/longbook')
    source = ROOT / 'pdf/UnderstandingDeepLearning_02_09_26_C.pdf'
    result = header('longbook')
    result['source'] = file_info(source)
    app = create_app(data_dir=root / 'records')
    with TestClient(app) as client:
        value = result['upload'] = upload(client, source)
        result['parsed'] = parsed_details(client, root / 'records', value)
        pid = 'paper-' + result['source']['sha256']
        result['status'] = read(client, f'/api/v1/papers/{pid}/parse-status')
        result['pagination'] = {name: read(client, path) for name, path in (
            ('papers', '/api/v1/papers?page=1&page_size=100'),
            ('chunks', f'/api/v1/papers/{pid}/chunks?page=1&page_size=100'))}
    records = root / 'records'
    result['status_histories'] = [json.loads(p.read_text(encoding='utf-8')) for p in (records / 'jobs').glob('job-*/parse-status.json')]
    entered = any(s['status'] == 'indexing' for h in result['status_histories'] for s in h)
    result['indexing'] = {'entered': entered, 'elapsed_seconds': None, 'reason': '未进入索引，不能将未运行记为0秒。'}
    result['published_chunks'] = sum(len(json.loads(p.read_text(encoding='utf-8'))) for p in (records / 'papers').glob('*/chunks.json'))
    result['page_limit_rejected'] = value['response'].get('error_code') == 'PARSE_FAILED' and '200' in value['response'].get('message', '')
    result['diagnosis'] = {'source': 'backend/scholar_graph/pipeline.py:124-125',
        'condition': 'if count < 1 or count > 200:', 'note': '在_inspect读取物理页数后、MinerU与索引前拒绝；本探针不绕过上限。'}
    result['source_after'] = file_info(source)
    result['conclusion'] = '失败：官方 pdf/ 真文件541页长书被200页上限拒绝，未产出Chunk或索引。' if result['page_limit_rejected'] else '需核对实际输出，不预判通过。'
    save(ROOT / 'tests/reports/official-pdf-longbook.json', result)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    main()

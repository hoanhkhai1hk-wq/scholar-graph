"""官方 pdf/ 真文件：按v7、v1顺序真实上传；身份查找仅旁观，不补元数据。"""
import json
import sys
from official_pdf_support import ROOT, prepare, header, save, file_info, upload, parsed_details, read
sys.path.insert(0, str(ROOT / 'backend'))
from fastapi.testclient import TestClient
from scholar_graph.api import create_app
from scholar_graph.storage import RecordStore
from scholar_graph.dedup import similarity


def main():
    root = prepare(ROOT / 'data/official-pdf/dedup')
    report = ROOT / 'tests/reports/official-pdf-dedup.json'
    result = header('dedup-v7-then-v1')
    result.update(uploads=[], identity_lookups=[])
    original = RecordStore.previous_version

    def observe(store, paper):
        prior = original(store, paper)
        result['identity_lookups'].append({'paper_id': paper['id'], 'identity': {
            name: paper[name] for name in ('title', 'authors', 'doi', 'arxiv_id', 'version')},
            'matched_paper_id': prior['paper_meta']['id'] if prior else None})
        return prior

    app = create_app(data_dir=root / 'records')
    bundles = []
    with TestClient(app) as client:
        RecordStore.previous_version = observe
        try:
            for name in ('1706.03762v7.pdf', '1706.03762v1.pdf'):
                source = ROOT / 'pdf' / name
                value = {'source': file_info(source), **upload(client, source)}
                value['parsed'] = parsed_details(client, root / 'records', value)
                if value['http_status'] == 201:
                    pid = value['response']['id']
                    value['decision'] = read(client, f'/api/v1/papers/{pid}/dedup-decision')
                    value['diff'] = read(client, f'/api/v1/papers/{pid}/diff-summary')
                    bundles.append(app.state.repository.paper(pid))
                value['source_after'] = file_info(source)
                result['uploads'].append(value)
                save(report, result)
        finally:
            RecordStore.previous_version = original
    result['offline_diagnostic'] = {'published': False, 'not_an_upload_warning': True,
        'dice': similarity(*bundles) if len(bundles) == 2 else None,
        'note': '仅在上传结束后对实际落盘Chunk计算词频Dice，未触发/写入裁决，不代表语义向量去重。'}
    result['warning'] = {'triggered': False, 'original_text': None,
        'reason': '真实响应只有PaperMeta，没有预警字段；裁决与差异GET原始响应逐次保存。'}
    result['diagnosis'] = {'metadata': 'backend/scholar_graph/pipeline.py:139-147',
        'identity_lookup': 'backend/scholar_graph/storage.py:83-111',
        'missing_step': 'backend/scholar_graph/pipeline.py:96-100',
        'note': '真实previous_version调用返回None，精确DOI/arXiv或完整标题作者身份未匹配；第97行条件跳过compare，第100行未写comparison。未运行全库词频/向量候选查找，也没有版本质量排序。没有去重判定/差异摘要可原文返回，不能拿离线Dice冒充。'}
    result['conclusion'] = '失败：官方 pdf/ 真文件上传未触发去重预警，未产生保留新版建议或差异摘要。'
    save(report, result)
    print(json.dumps({'scope': result['scope'], 'uploads': [(v['http_status'], v['parsed']) for v in result['uploads']], 'diagnostic': result['offline_diagnostic']}, ensure_ascii=False))


if __name__ == '__main__':
    main()

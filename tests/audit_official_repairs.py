"""官方 pdf/ 真文件修复验收：核对真实产出、锚点、预警、批次索引与回归。"""
import hashlib
import json
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

from official_pdf_support import ROOT, SCOPE, save, file_info
sys.path.insert(0, str(ROOT / 'backend'))
from scholar_graph.api_repository import ApiRepository
from scholar_graph.chunk_index import ChunkIndex
from scholar_graph.validation import ContractGate
from run_official_repairs import BASELINE


def git(*args):
    return subprocess.check_output(['git', *args], cwd=ROOT, encoding='utf-8').strip()


def main():
    reports = ROOT / 'tests/reports'
    gate, checks = ContractGate(), []
    def require(name, value):
        checks.append({'check': name, 'passed': bool(value)})
        if not value:
            raise AssertionError(name)
    cases = {}
    for case in ('dedup', 'ocr', 'longbook'):
        value = json.loads((reports / f'official-pdf-repair-{case}.json').read_text(encoding='utf-8'))
        require(case + ':官方真文件标记与真实成功', value['scope'] == SCOPE and value['baseline'] == BASELINE and value['passed'])
        require(case + ':无真实模型API', value['real_llm_calls'] == 0 and value['real_api_keys_used'] is False)
        repo = ApiRepository(ROOT / 'data/official-repair' / case / 'records', gate)
        bundles = []
        before_repair = json.loads((reports / f'official-pdf-{case}.json').read_text(encoding='utf-8'))
        for ordinal, upload in enumerate(value['uploads']):
            require(case + ':语料未修改', upload['source'] == upload['source_after'] == file_info(Path(upload['source']['file'])))
            require(case + ':源路径为官方pdf目录', Path(upload['source']['file']).parent == ROOT / 'pdf')
            original = before_repair['uploads'][ordinal]['source'] if case == 'dedup' else before_repair['source']
            require(case + ':与修复前同一份真文件', upload['source']['sha256'] == original['sha256'])
            require(case + ':201且完成100%', upload['http_status'] == 201 and upload['status']['response']['status'] == 'completed' and upload['status']['response']['progress'] == 100)
            pid = upload['response']['id']
            bundle = repo.paper(pid)
            gate.bundle(bundle)
            require(case + ':非空真实文本及契约数量一致', len(bundle['chunks']) == upload['parsed']['record_counts']['Chunk'] > 0 and all(c['text'].strip() for c in bundle['chunks']))
            bundles.append(bundle)
            if case != 'dedup':
                metrics = upload['batch_metrics']
                require(case + ':完整物理页处理且无失败页', metrics['completed_pages'] == list(range(1, bundle['paper_meta']['page_count'] + 1)) and metrics['failed_pages'] == [])
                require(case + ':解析中即可读取已发布Chunk', any(o['status']['status'] in ('parsing', 'ocr') and o['chunks_http'] == 200 and o['published_chunks'] > 0 for o in upload['observations']))
                require(case + ':分批SQLite索引数量一致', ChunkIndex(repo.root, pid).page(1, 1)['total'] == len(bundle['chunks']) == metrics['published_chunks'])
                require(case + ':索引确实运行', metrics['indexing_seconds'] > 0)
                require(case + ':越界分页为空', upload['chunks_overflow']['http_status'] == 200 and upload['chunks_overflow']['response']['items'] == [])
                require(case + ':内存与耗时有实测采样', upload['measurement']['sample_count'] > 1 and upload['measurement']['rss_peak_bytes'] > 0 and upload['measurement']['elapsed_seconds'] > 0)
        cases[case] = {'bundle_counts': [len(b['chunks']) for b in bundles],
                       'rss_peak_mib': [u['measurement']['rss_peak_bytes'] / 1048576 for u in value['uploads']],
                       'elapsed_seconds': [u['measurement']['elapsed_seconds'] for u in value['uploads']]}
        if case == 'dedup':
            last = value['uploads'][-1]
            require('去重:第二传有保留v7预警原文', '建议保留库里较新版本（v7）' in last['warning_text'])
            require('去重:裁决与摘要不再404', last['decision']['http_status'] == last['diff']['http_status'] == 200)
            require('去重:按新上传id落盘且保留库内版本', last['decision']['response']['new_paper_id'] == last['response']['id'] and last['decision']['response']['recommendation'] == 'keep_old')
            gate.comparison(last['decision']['response'], last['diff']['response'], bundles)
            require('去重:真实身份和版本来自文件', [b['paper_meta']['arxiv_id'] for b in bundles] == ['1706.03762v7', '1706.03762v1'])
        elif case == 'ocr':
            require('OCR:全部15页有真实Chunk', {c['page_number'] for c in bundles[0]['chunks']} == set(range(1, 16)))
            require('OCR:存在真实标题识别文本', any('attention is all you need' in c['text'].casefold() for c in bundles[0]['chunks']))
        else:
            require('长书:完整541页与17批', bundles[0]['paper_meta']['page_count'] == 541 and len(value['uploads'][0]['batch_metrics']['batches']) == 17)
            require('长书:页数上限默认覆盖541', value['uploads'][0]['batch_metrics']['limits']['max_pages'] >= 541)
            require('长书:尾页可取', value['uploads'][0]['chunks_last']['response']['items'][-1]['page_number'] == 541)

    frozen = []
    for name in git('ls-tree', '-r', '--name-only', BASELINE, 'contracts').splitlines():
        before, after = git('rev-parse', BASELINE + ':' + name), git('hash-object', name)
        require(name + ':契约原样保留', before == after)
        frozen.append({'file': name, 'blob': after})
    changes = git('diff', BASELINE, '--name-status').splitlines()
    new = git('ls-files', '--others', '--exclude-standard').splitlines()
    require('只改后端并新增测试证据', all(line.split('\t')[-1].startswith(('backend/', 'tests/')) for line in changes) and all(p.startswith(('backend/', 'tests/')) for p in new))
    require('旧官方报告零改动', not git('diff', BASELINE, '--name-only', 'tests/reports/official-pdf-acceptance.md', 'tests/reports/official-pdf-dedup.json', 'tests/reports/official-pdf-ocr.json', 'tests/reports/official-pdf-longbook.json'))
    require('pdf目录忽略且无跟踪文件', '/pdf/' in git('check-ignore', '-v', 'pdf/probe.txt') and not git('ls-files', 'pdf'))
    paths = sorted(set([line.split('\t')[-1] for line in changes] + new))
    pattern = re.compile(rb'(?:sk-[A-Za-z0-9]{24,}|hf_[A-Za-z0-9]{24,}|ghp_[A-Za-z0-9]{24,}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----)')
    require('改动文件无常见密钥格式', not any(pattern.search((ROOT / p).read_bytes()) for p in paths))
    suites = ET.parse(reports / 'official-pdf-repair-pytest.xml').getroot().findall('testsuite')
    regression = {k: sum(int(s.get(k, '0')) for s in suites) for k in ('tests', 'failures', 'errors', 'skipped')}
    require('全量回归含新增用例且零失败零跳过', regression['tests'] >= 306 and regression['failures'] == regression['errors'] == regression['skipped'] == 0)
    output = {'scope': SCOPE, 'baseline': BASELINE, 'source_commit': git('rev-parse', 'HEAD'),
              'business_cases_passed': 3, 'business_cases_failed': 0, 'checks': checks,
              'contract_files_unchanged': frozen, 'regression': regression, 'cases': cases,
              'changed_paths': paths, 'secret_pattern_matches': 0,
              'notes': '真实产出经过原Schema/锚点门禁；未修改前端/旧契约/旧报告；索引为本地SQLite物理页索引，不声称语义向量去重。'}
    save(reports / 'official-pdf-repair-audit.json', output)
    print(json.dumps({'checks_passed': len(checks), 'business_cases_passed': 3, 'regression': regression, 'cases': cases}, ensure_ascii=False))


if __name__ == '__main__':
    main()

"""官方 pdf/ 真文件：复核原始探针、落盘记录、语料哈希、回归与只增验证文件边界。"""
import hashlib
import json
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

from official_pdf_support import ROOT, BASELINE, SCOPE, save, file_info
sys.path.insert(0, str(ROOT / 'backend'))
from scholar_graph.api_repository import ApiRepository
from scholar_graph.validation import ContractGate
from scholar_graph.dedup import similarity

REPORTS = ROOT / 'tests/reports'


def git(*args):
    return subprocess.check_output(['git', *args], cwd=ROOT, encoding='utf-8').strip()


def load(name):
    return json.loads((REPORTS / name).read_text(encoding='utf-8'))


def main():
    checks = []

    def require(label, condition):
        checks.append({'check': label, 'passed': bool(condition)})
        if not condition:
            raise AssertionError(label)

    values = {name: load(f'official-pdf-{name}.json') for name in ('dedup', 'ocr', 'longbook')}
    gate = ContractGate()
    sources = []
    for name, value in values.items():
        require(name + ':官方语料与基线标记', value['scope'] == SCOPE and value['baseline'] == BASELINE)
        require(name + ':无真实模型API调用', value['real_llm_calls'] == 0 and value['real_api_keys_used'] is False)
        entries = value['uploads'] if name == 'dedup' else [value]
        for entry in entries:
            source, after = entry['source'], entry['source_after']
            path = Path(source['file']).resolve()
            require(name + ':直接读取官方pdf目录', path.parent == (ROOT / 'pdf').resolve())
            actual = file_info(path)
            require(path.name + ':运行前后及审计时哈希一致', source == after == actual)
            sources.append(actual)

    d, o, b = (values[k] for k in ('dedup', 'ocr', 'longbook'))
    repo = ApiRepository(ROOT / 'data/official-pdf/dedup/records', gate)
    bundles = []
    require('上传顺序v7然后v1', [Path(v['source']['file']).name for v in d['uploads']] == ['1706.03762v7.pdf', '1706.03762v1.pdf'])
    for value in d['uploads']:
        require('真实上传201', value['http_status'] == 201)
        bundle = repo.paper(value['response']['id'])
        gate.bundle(bundle)
        bundles.append(bundle)
        for field, record in (('chunks', 'Chunk'), ('reference_entries', 'ReferenceEntry'), ('citation_links', 'CitationLink')):
            require(record + ':发布记录与接口总数一致', len(bundle[field]) == value['parsed']['record_counts'][record])
        for key in ('decision', 'diff'):
            require(key + ':实际无记录404', value[key]['http_status'] == 404)
            gate.error(value[key]['response'])
        require('完成状态合法', value['parsed']['latest_status']['response']['status'] == 'completed')
    require('身份查找真实未命中', len(d['identity_lookups']) == 2 and all(v['matched_paper_id'] is None for v in d['identity_lookups']))
    require('Dice仅离线诊断', d['offline_diagnostic']['published'] is False and d['offline_diagnostic']['dice'] == similarity(*bundles))
    require('无上传预警', d['warning']['triggered'] is False and d['warning']['original_text'] is None)
    require('未发布比较记录', not list((repo.root / 'comparisons').glob('comparison-*')))

    require('官方扫描件15页无文本层', o['source']['physical_pages'] == 15 and o['text_layer_chars_by_page'] == [0] * 15)
    require('OCR使用默认300秒且进入分支', o['default_api_configuration'] and o['engine_timeout_seconds'] == 300 and o['ocr_branch_entered'])
    require('OCR实际调用已记录', any(v['mode'] == 'ocr' for v in o['engine_calls']))
    for name, value in (('ocr', o), ('longbook', b)):
        root = ROOT / 'data/official-pdf' / name / 'records'
        require(name + ':记录失败而非通过', value['upload']['http_status'] == 422 and value['conclusion'].startswith('失败'))
        gate.error(value['upload']['response'])
        published = sum(len(json.loads(p.read_text(encoding='utf-8'))) for p in (root / 'papers').glob('*/chunks.json'))
        require(name + ':未发布Chunk', published == 0 == value.get('effective_chunks', value.get('published_chunks')))
        actual_histories = [json.loads(p.read_text(encoding='utf-8')) for p in (root / 'jobs').glob('job-*/parse-status.json')]
        require(name + ':报告与实际失败历史一致', actual_histories == value['status_histories'] and all(h[-1]['status'] == 'failed' for h in actual_histories))
        for history in actual_histories:
            for status in history:
                gate.record('ParseStatus', status)
    require('扫描件真实错误OCR_FAILED', o['upload']['response']['error_code'] == 'OCR_FAILED')
    require('长书完整541页22344992字节', (b['source']['physical_pages'], b['source']['bytes']) == (541, 22344992))
    require('长书未进入索引且被200页拒绝', b['page_limit_rejected'] and b['indexing'] == {'entered': False, 'elapsed_seconds': None, 'reason': '未进入索引，不能将未运行记为0秒。'})
    require('无长书分页成功伪报', b['pagination']['papers']['response']['total'] == 0 and b['pagination']['chunks']['http_status'] == 404)

    frozen = []
    for name in git('ls-tree', '-r', '--name-only', BASELINE, 'contracts').splitlines():
        expected, actual = git('rev-parse', BASELINE + ':' + name), git('hash-object', name)
        require(name + ':契约零改动', expected == actual)
        frozen.append({'file': name, 'git_blob': actual})
    require('官方语料未被跟踪', not git('ls-files', 'pdf'))
    require('pdf目录整体被忽略', '/pdf/' in (ROOT / '.gitignore').read_text(encoding='utf-8').splitlines() and '/pdf/' in git('check-ignore', '-v', 'pdf/non-pdf-sentinel.txt'))
    changes = git('diff', BASELINE, '--name-status').splitlines()
    new = git('ls-files', '--others', '--exclude-standard').splitlines()
    paths = sorted(set([line.split('\t')[-1] for line in changes] + new + ['tests/reports/official-pdf-audit.json']))
    require('只新增tests与忽略规则', all((line == 'M\t.gitignore' or line.startswith('A\ttests/')) for line in changes) and all(p.startswith('tests/') for p in new))
    pattern = re.compile(rb'(?:sk-[A-Za-z0-9]{24,}|hf_[A-Za-z0-9]{24,}|ghp_[A-Za-z0-9]{24,}|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----|[?&](?:jwt|sig)=)')
    require('新增文件无常见密钥格式', not [p for p in paths if (ROOT / p).exists() and pattern.search((ROOT / p).read_bytes())])

    suites = ET.parse(REPORTS / 'official-pdf-pytest.xml').getroot().findall('testsuite')
    regression = {key: sum(int(s.get(key, '0')) for s in suites) for key in ('tests', 'failures', 'errors', 'skipped')}
    regression['passed'] = regression['tests'] - regression['failures'] - regression['errors'] - regression['skipped']
    require('全量既有296项回归无失败无跳过', regression == {'tests': 296, 'failures': 0, 'errors': 0, 'skipped': 0, 'passed': 296})
    for path in ('official-pdf-pytest.xml', 'official-pdf-acceptance.md'):
        require(path + ':官方验证标识', SCOPE in (REPORTS / path).read_text(encoding='utf-8'))
    narrative = (REPORTS / 'official-pdf-acceptance.md').read_text(encoding='utf-8')
    require('总报告无未填占位', not re.search(r'__[A-Z_]+__', narrative))
    require('总报告关键数字与原始JSON一致', all(str(number) in narrative for number in (
        o['upload']['measurement']['elapsed_seconds'], b['upload']['measurement']['rss_peak_bytes'],
        b['upload']['measurement']['rss_peak_bytes'] / 1048576, d['offline_diagnostic']['dice'], regression['passed'])))
    old_d = load('public-equivalent-dedup.json')
    old_o = load('public-equivalent-ocr.json')
    old_x = load('public-equivalent-ocr-extended.json')
    old_b = load('public-equivalent-longbook.json')
    comparison = {
        'dedup_chunks': {'previous': [v['parsed']['record_counts']['Chunk'] for v in old_d['raw_uploads']],
                         'official': [v['parsed']['record_counts']['Chunk'] for v in d['uploads']]},
        'dice': {'previous': old_d['fetch_controls'][-1]['comparison']['decision']['response']['similarity'], 'official_offline_only': d['offline_diagnostic']['dice'],
                 'note': '上一单Dice来自另一次带arXiv身份抓取控制，本单Dice为离线诊断；两者都不能当作本单上传预警。'},
        'ocr_seconds': {'previous': [v['upload']['measurement']['elapsed_seconds'] for v in (old_o, old_x)], 'official': o['upload']['measurement']['elapsed_seconds']},
        'ocr_input_same_sha256': o['source']['sha256'] == old_o['scan']['sha256'],
        'book_rss_peak_mib': {'previous': old_b['upload']['measurement']['rss_peak_bytes'] / 1048576, 'official': b['upload']['measurement']['rss_peak_bytes'] / 1048576},
        'text_and_book_sha256_same_as_previous': [d['uploads'][i]['source']['sha256'] == old_d['sources'][i]['sha256'] for i in range(2)] + [b['source']['sha256'] == old_b['source']['sha256']]}
    output = {'scope': SCOPE, 'baseline': BASELINE, 'audit_source_commit': git('rev-parse', 'HEAD'),
              'evidence_consistency_checks_passed': True, 'business_cases_passed': 0, 'business_cases_failed': 3,
              'checks': checks, 'frozen_contract_files': frozen, 'sources': sources, 'changed_paths': paths,
              'regression': regression, 'comparison': comparison,
              'limits': '审计核对失败证据不代表业务通过；RSS为50ms采样的进程树合计；常见密钥模式检查不覆盖所有秘密，未读取.env。'}
    save(REPORTS / 'official-pdf-audit.json', output)
    print(json.dumps({'scope': SCOPE, 'checks_passed': len(checks), 'regression': regression, 'comparison': comparison}, ensure_ascii=False))


if __name__ == '__main__':
    main()

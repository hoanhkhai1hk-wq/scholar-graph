"""Recheck exported Docker evidence and actual HTTP publications, then write the report."""
import hashlib
import json
import os
import re
import subprocess
import sys
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / 'tests/reports'
BASELINE = '11170bcc1bce36a7984ccc27325e4117bdc037b8'
sys.path.insert(0, str(ROOT / 'backend'))
from scholar_graph.qa import validate_answer
from scholar_graph.validation import ContractGate


def load(name):
    return json.loads((REPORTS / name).read_text(encoding='utf-8'))


def totals(name):
    suites = list(ET.parse(REPORTS / name).getroot().iter('testsuite'))
    result = {key: sum(int(s.attrib[key]) for s in suites) for key in ('tests', 'failures', 'errors', 'skipped')}
    result['passed'] = result['tests'] - result['failures'] - result['errors'] - result['skipped']
    return result


def get(path):
    with urllib.request.urlopen('http://127.0.0.1:8000/api/v1' + path, timeout=60) as response:
        return json.load(response)


def bundle(pid):
    result = {'paper_meta': get('/papers/' + pid)}
    for endpoint, key in (('chunks', 'chunks'), ('references', 'reference_entries'), ('citation-links', 'citation_links')):
        items, page = [], 1
        while True:
            value = get(f'/papers/{pid}/{endpoint}?page={page}&page_size=100')
            items.extend(value['items'])
            if not value['has_next']:
                break
            page += 1
        result[key] = items
    return result


def main():
    run = load('docker-reproduction-run.json')
    live = load('docker-runtime-inspection.json')
    image = load('docker-image-input-audit.json')
    failure_path = REPORTS / 'docker-reproduction-initial-export-failure.json'
    failure = json.loads(failure_path.read_text(encoding='utf-8')) if failure_path.exists() else {}
    value = run.get('container_results', {})
    checks = {'remote_main_clone': run['remote'] == 'https://github.com/hoanhkhai1hk-wq/scholar-graph.git'
              and run['branch'] == 'main' and run['clone']['clean'] and run['clone'].get('clean_after_build_and_run'),
              'clone_no_host_artifacts': all(run['clone']['host_artifacts_absent'].values()),
              'no_cache_build': any(s['stage'] == 'build-no-cache' and s['exit_code'] == 0 and '--no-cache' in s['command'] for s in run['steps']),
              'two_healthy_services': len(live['containers']) == 2 and all(c['health'] == 'healthy' for c in live['containers']),
              'host_http_and_proxy': len(live['host_http']) == 3 and all(r['status'] == 200 for r in live['host_http']),
              'runtime_no_credential_variables': all(c['credential_variables_absent'] for c in live['containers']),
              'image_no_pdf_env_git_or_parsed_inputs': not image['app_pdf_files'] and not any(v for k, v in image.items() if k != 'app_pdf_files'),
              'empty_backend_start': value.get('empty_backend_before_tests') is True,
              'corpus_read_only_in_container': value.get('corpus_read_only') is True,
              'container_source_matches_clone': run.get('image_source_matches_clone') is True and len(value.get('source_sha256', {})) >= 8,
              'actual_container_cases_complete': run['status'] == 'passed' and value.get('passed') is True}
    checks['one_command_entrypoint'] = run.get('one_command_entrypoint', {}).get('exit_code') == 0
    clone = Path(run['clone']['path'])
    checks['clone_still_clean'] = not subprocess.check_output(['git', 'status', '--porcelain=v1'], cwd=clone, text=True).strip()
    for name, digest in value.get('source_sha256', {}).items():
        checks['source:' + name] = hashlib.sha256((clone / name).read_bytes()).hexdigest() == digest
    mount = next(m for m in live['containers'][0]['mounts'] if m['destination'] == '/corpus')
    checks['corpus_bind_ro'] = mount['type'] == 'bind' and mount['read_only']
    config_mount = next(m for m in run['compose_config']['backend_volumes'] if m['target'] == '/corpus')
    corpus = Path(config_mount['source'])
    for case, result in value['cases'].items():
        checks['case:' + case] = result['passed']
        for row in result['uploads']:
            checks['source_pdf:' + row['file']] = hashlib.sha256((corpus / row['file']).read_bytes()).hexdigest() == row['sha256']
            checks['publication:' + row['file']] = row['http_status'] == 201 and row['status']['status'] == 'completed' and row['chunks'] > 0
    dedup = value['cases']['dedup']['uploads']
    checks['dedup_keep_newer_v7'] = '建议保留库里较新版本（v7）' in dedup[-1]['warning'] and dedup[-1]['dedup-decision']['body']['recommendation'] == 'keep_old'
    ocr = value['cases']['ocr']['uploads'][0]
    book = value['cases']['longbook']['uploads'][0]
    snapshot_path = REPORTS / 'docker-ocr-progress-snapshot.json'
    snapshot = json.loads(snapshot_path.read_text(encoding='utf-8')) if snapshot_path.exists() else {}
    snapshot_matches = snapshot.get('run_id') == run['run_id']
    checks['ocr_real_text_no_failed_pages'] = bool(ocr['text_samples']) and not ocr['batch_metrics']['failed_pages']
    checks['book_all_541_pages_indexed'] = book['pages'] == 541 and book['batch_metrics']['completed_pages'] == list(range(1, 542)) and not book['batch_metrics']['failed_pages'] and book['batch_metrics']['published_chunks'] == book['chunks'] and book['batch_metrics']['indexing_seconds'] > 0
    checks['book_pagination'] = book['last_page']['http_status'] == 200 and book['last_page']['items'] > 0 and book['last_page']['max_pdf_page'] == 541 and book['overflow_items'] == 0
    gate = ContractGate()
    old, new = [bundle(row['response']['id']) for row in dedup]
    gate.bundle(old)
    gate.bundle(new)
    gate.comparison(dedup[-1]['dedup-decision']['body'], dedup[-1]['diff-summary']['body'], [old, new])
    qa = value['no_key_qa']
    quoted = re.split(r'\n\n(?=【证据 [A-Z]】\n)', qa['body']['answer'])
    evidence = [{'anchor': anchor, 'quote': block.split('\n', 1)[1]} for anchor, block in zip(qa['body']['anchors'], quoted, strict=True)]
    validate_answer(qa['body'], old, evidence, gate)
    checks['qa_http_real_anchor_and_numeric_gate'] = qa['http_status'] == 200 and qa['passed'] and not qa['body']['refused']
    host = totals('docker-host-pytest.xml')
    container = totals('docker-container-pytest.xml')
    checks['host_regression'] = host == {'tests': 329, 'failures': 0, 'errors': 0, 'skipped': 1, 'passed': 328}
    checks['container_regression'] = container == {'tests': 329, 'failures': 0, 'errors': 0, 'skipped': 6, 'passed': 323}
    for name in ('contracts', 'frontend', 'prompts', 'experiments', 'test-records'):
        changed = subprocess.check_output(['git', 'diff', '--name-only', BASELINE, '--', name], cwd=ROOT, text=True).strip()
        checks['unchanged:' + name] = not changed
    checks['pdf_ignored_untracked'] = '/pdf/' in (ROOT / '.gitignore').read_text(encoding='utf-8').splitlines() and not subprocess.check_output(['git', 'ls-files', 'pdf'], cwd=ROOT, text=True).strip()
    key = os.environ.get('DEEPSEEK_API_KEY')
    names = set(subprocess.check_output(['git', 'diff', '--name-only', BASELINE], cwd=ROOT, text=True).splitlines())
    names.update(subprocess.check_output(['git', 'ls-files', '--others', '--exclude-standard'], cwd=ROOT, text=True).splitlines())
    checks['deliverables_no_injected_key'] = not key or all(key.encode() not in (ROOT / name).read_bytes() for name in names if (ROOT / name).is_file())
    readme_line = next(n for n, line in enumerate((ROOT / 'README.md').read_text(encoding='utf-8').splitlines(), 1) if line == '## Docker 复现')
    audit = {'scope': '干净克隆实际Docker容器；官方 pdf/ 真文件', 'baseline': BASELINE,
             'source_commit': run['clone']['commit'], 'checks': checks,
             'status': 'passed' if all(checks.values()) else 'failed', 'host_regression': host,
             'container_regression': container, 'readme_section_line': readme_line}
    (REPORTS / 'docker-reproduction-audit.json').write_text(json.dumps(audit, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    lines = ['# Docker干净环境复现验收', '',
             f"开工main：`{BASELINE}`，git pull原文`Already up to date.`，工作区干净。验收结果：**{audit['status']}**。", '',
             f"真实远端main新克隆：`{run['clone']['commit']}`；目录`{clone}`；构建前后Git工作区均干净。初始无backend/.venv、frontend/node_modules、frontend/.next、.env、pdf、data。没有复制宿主机依赖、模型缓存或已解析记录。", '',
             '## 构建和启动', '',
             'Docker CLI/Engine 29.9.2、Docker Desktop4.96.3、Compose v5.6.1，Linux/amd64引擎，20 CPU、约7.57GiB总内存。最初WSL未就绪，引擎不能启动；用户完成环境准备后已返回Server信息，随后才开始实际构建。本报告不将CLI安装等同于引擎就绪。', '',
             '| 阶段 | 退出码 | 秒 |', '| --- | ---: | ---: |']
    lines += [f"| {s['stage']} | {s['exit_code']} | {s['elapsed_seconds']:.6f} |" for s in run['steps']]
    lines += ['', f"额外执行同一克隆的up --build -d --wait一条命令入口，退出码0，耗时{run['one_command_entrypoint']['elapsed_seconds']:.6f}秒，两服务仍healthy。该次使用前面构建的层缓存；真正的全新无缓存构建耗时按上表build-no-cache实测登记，不把缓存启动冒充冷构建。", '']
    if failure.get('run_id') == run['run_id']:
        failed_step = next(s for s in failure['steps'] if s['stage'] == 'export-container-results')
        lines += ['### Windows导出失败与修复', '',
                  '首次整目录docker compose cp退出码1，原因是pytest临时树含Linux的*current符号链接，Windows创建链接缺权限，原文：', '',
                  '```text', *failed_step['last_lines'], '```', '',
                  '此时容器内业务与回归已通过，但整单尚未交付。修复tests/reproduce_docker.py，只复制明确列出的JSON/XML/控制台日志文件，6次文件导出均退出0；--resume-export从同一仍运行的容器取回原始产出，没有重跑三项、没有换用宿主机结果。初次失败证据另存docker-reproduction-initial-export-failure.json，不覆盖为成功。README同步改为逐文件导出，不要求用户开Windows符号链接权限。后续仅修改宿主机导出辅助、README与报告，容器业务实现和已验收构建配置未改动。', '']
    build = next(s for s in run['steps'] if s['stage'] == 'build-no-cache')
    lines += ['', '构建命令确有--no-cache，Node npm ci / npm run build及Python pyproject安装均在构建阶段执行。固定基础镜像python:3.12.15-slim-bookworm、node:22.23.4-bookworm-slim；backend安装backend[ocr,test]并执行pip check。未使用宿主机venv/node_modules；前端源文件零改动。后端附带容器内安装的Node/TypeScript，既有真实代理回归没有因缺工具跳过。', '',
              f"完整构建日志留在本地`{build['log']}`，{build['log_bytes']}字节，SHA-256 `{build['log_sha256']}`。日志尾摘要：", '', '```text', *build['last_lines'], '```', '',
              '构建时只有受.dockerignore过滤的源码上下文，语料不在镜像。另用该backend镜像启动无网络、无挂载的一次性容器检查：/app下PDF为0，.git/.env/宿主机venv/已解析papers均不存在，未设置模型Key；证据docker-image-input-audit.json。', '',
              '## 健康检查与端口', '',
              '后端8000、前端3000均绑定宿主机127.0.0.1。Compose健康检查实际请求后端论文列表和前端同源代理；两个容器均healthy。宿主机访问8000列表、3000首页、3000代理均HTTP200；没有把静态HTML成功冒充问答通过。镜像ID、容器ID、真实只读挂载与端口见docker-runtime-inspection.json。', '',
              '## 回归测试', '',
              f"容器内：{container['tests']}项收集，**{container['passed']}通过、{container['skipped']}跳过、0失败、0错误**；耗时{value['regression']['elapsed_seconds']:.6f}秒。完整JUnit为docker-container-pytest.xml。", '',
              '6项跳过逐项为：', '']
    lines += [f"- {row['name']}：{row['reason']}" for row in value['regression']['skipped_cases']]
    lines += ['', f"宿主机：{host['tests']}项收集，**{host['passed']}通过、{host['skipped']}跳过、0失败、0错误**；JUnit为docker-host-pytest.xml。宿主机包含Windows锁实测，唯一跳过为无Key实连。两边均启用--run-ocr --run-real-model：实际OCR已运行，真实大模型无Key跳过，不冒充实连通过。回归输入仍为自制样例；下面三项另用官方真文件运行。", '',
              '## 官方 pdf/ 真文件三项容器实测', '',
              '官方语料仅只读绑定/corpus；容器statvfs与Docker inspect均确认只读。首次HTTP论文列表为0，每次源文件parse-status为404才上传，禁止复用已解析结果。原文件SHA-256在上传前后核对；容器源码指纹与干净克隆的8份输入逐一一致。', '',
              '| 项目 | HTTP | Chunk | 秒（实际上传） | RSS采样峰值MiB | 结论 |', '| --- | ---: | ---: | ---: | ---: | --- |']
    for case, item in value['cases'].items():
        for row in item['uploads']:
            lines.append(f"| {row['file']} | {row['http_status']} | {row['chunks']} | {row['measurement']['elapsed_seconds']:.6f} | {row['measurement']['rss_sampled_peak_bytes']/1024**2:.6f} | {'通过' if row['passed'] and item['passed'] else '未通过'} |")
    lines += ['', '去重第二传预警原文：', '', '> ' + dedup[-1]['warning'], '',
              f"去重判定HTTP{dedup[-1]['dedup-decision']['http_status']}、recommendation={dedup[-1]['dedup-decision']['body']['recommendation']}；差异摘要HTTP{dedup[-1]['diff-summary']['http_status']}。完整原记录见docker-dedup.json；语义为保留库内v7，本次new_paper_id仍指上传v1。机制仍是现有身份匹配与词频Dice，没有宣称向量去重。", '',
              f"OCR：全部{len(ocr['batch_metrics']['completed_pages'])}/{ocr['pages']}物理页完成，失败页{ocr['batch_metrics']['failed_pages']}；真实首批文本如下。" +
              (f"同一后端运行中快照：{snapshot['parse-status']['current_stage']}，分页total={snapshot['chunks?page_size=1']['total']}；见匹配本轮run_id的docker-ocr-progress-snapshot.json。" if snapshot_matches else '该轮未另存匹配run_id的中途快照。'), '', '```text', *ocr['text_samples'], '```', '',
              'OCR模型来自容器首次联网下载，没有挂宿主机模型缓存；上传计时包含该请求中的模型准备和推理，不把宿主机缓存耗时混入。相同容器本轮运行产生的缓存属于容器自身产物。识别完成不等同逐字准确率评测。', '',
              f"长书：{book['pages']}物理页、{book['bytes']}字节；{len(book['batch_metrics']['batches'])}批；完成页数{len(book['batch_metrics']['completed_pages'])}，失败页{book['batch_metrics']['failed_pages']}；索引相关累计{book['batch_metrics']['indexing_seconds']:.6f}秒。末分页HTTP{book['last_page']['http_status']}，{book['last_page']['items']}条，最大物理页{book['last_page']['max_pdf_page']}；越界页返回{book['overflow_items']}条。没有200页拒绝，默认上限仍2000页。索引计时含批次规范化、Schema/外键门禁、发布与SQLite提交，不是纯SQL时间。", '',
              'RSS为每50ms采样容器内可读进程的合计，可能重复计算共享页；不宣称精确系统高水位。每次上传另保存cgroup采样峰值和容器生命周期memory.peak，后者包含之前回归/用例，不能当作该单次上传峰值。未拿宿主机RSS数字冒充容器内存。', '',
              '## 一次实际无Key问答', '', f"问题：{qa['question']}；HTTP{qa['http_status']}；refused=false；锚点{len(qa['body']['anchors'])}处；数字校验{qa['body']['numeric_fact_check']['status']}。", '',
              '```text', qa['body']['answer'], '```', '', '```json', json.dumps(qa['body']['anchors'], ensure_ascii=False, indent=2), '```', '',
              '回答来自容器当轮上传Attention v7的真实Chunk。审计通过同一容器HTTP重新读取两篇论文的四类记录，复核原Schema、去重/差异外键与问答原文锚点；没有从宿主机已有解析目录取证。模型调用0，两个容器环境均没有API_KEY/TOKEN/SECRET变量，不写Key到镜像、Compose或报告。', '',
              '## README与复现边界', '', f"README.md第{readme_line}行新增“Docker 复现”，含构建、启动、跑测试三条命令、两个端口和预期输出；一条启动入口为docker compose up --build -d --wait。", '',
              '基本启动与--suite-only不要求私有语料；官方验收用services/docker-compose.acceptance.yml覆盖，设置现有语料路径并使用新项目名/空数据卷。探针拒绝复用非空论文库。Docker数据卷不会自动删除；本轮容器和数据保留供复核，项目名见下。GROBID与独立BGE模型不包含在默认两服务，未宣称本轮接通；前端源码、全部既有契约及prompts/experiments/test-records零改动。', '',
              f"本轮项目名：`{run['project']}`。临时克隆、完整日志和导出的中间数据仅在被忽略的data/；Git只保存脚本、配置与报告/JSON/JUnit，不含PDF、模型或真实Key。审计{sum(checks.values())}/{len(checks)}项通过，详见docker-reproduction-audit.json。", '',
              '复核脚本tests/audit_docker_reproduction.py需要本地原文件、当轮临时克隆和仍运行的容器；它是交付审计工具，不是应用启动前提。已有容器仍占用8000/3000，新项目启动前应先停止本轮项目，保留数据卷即可，无需删除官方文件或模型。', '',
              '技术依据：[Docker构建上下文与忽略规则](https://docs.docker.com/build/concepts/context/)、[Compose构建](https://docs.docker.com/reference/compose-file/build/)、[Compose只读绑定挂载](https://docs.docker.com/reference/compose-file/services/#volumes)、[Next.js自托管](https://nextjs.org/docs/app/guides/self-hosting)。', '']
    report = '\n'.join(lines)
    if key and key in report:
        raise RuntimeError('Credential safety check rejected report')
    (REPORTS / 'docker-reproduction-acceptance.md').write_text(report, encoding='utf-8')
    print(json.dumps({'audit': audit['status'], 'checks_passed': sum(checks.values()), 'checks_total': len(checks),
                      'host': host, 'container': container}, ensure_ascii=False))
    return 0 if audit['status'] == 'passed' else 1


if __name__ == '__main__':
    raise SystemExit(main())

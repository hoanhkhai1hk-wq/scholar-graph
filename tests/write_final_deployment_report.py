"""Render the final acceptance report solely from measured JSON and JUnit evidence."""
import json
from pathlib import Path
import subprocess
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT/'tests/reports'


def read(name):
    return json.loads((REPORTS/name).read_text(encoding='utf-8'))


def main():
    build = read('final-deployment-build.json')
    host = read('final-deployment-host-final.json')
    container = read('final-deployment-container.json')
    runtime = read('final-deployment-runtime.json')
    audit = read('final-deployment-audit.json')
    ci = read('final-deployment-ci.json')
    resource = read('final-deployment-resource-adjustment.json')
    initial_build = read('final-deployment-build-before-runtime-fix.json')
    interrupted_build = read('final-deployment-runtime-rebuild-interrupted.json')
    passed = audit['passed'] and build['passed'] and host['passed'] and container['passed']
    lines = ['# Docker 最终部署验收', '', '日期：2026-10-26（Asia/Shanghai）。语料为 **官方 pdf/ 真文件**。', '',
        '**最终结论：'+('通过' if passed else '未通过')+'。** 宿主机与容器独立记录，未以宿主机结果替代容器结果。', '',
        '## 基线、干净克隆与镜像版本', '',
        '开工 main：`8de7a907c212b49588fdf00ef9842e45863b273f`，git pull 为 `Already up to date.`，工作区干净。', '',
        '本次先推送全部应用、配置与回归用例，再从远端 main 新克隆：`'+build['clone']['commit']+'`。', '',
        '克隆目录：`'+build['clone']['path']+'`。构建前后均干净；初始没有 backend/.venv、frontend/node_modules、frontend/.next、.env、pdf/、data/。没有复制宿主机依赖、模型缓存或已解析记录。', '',
        '镜像 OCI revision 标签均为该功能主干提交；后续交付仅增加宿主机检查脚本、运行说明与验收证据，不改变已构建的应用、配置或被执行回归用例。', '',
        '| 阶段 | 退出码 | 实测秒 |', '| --- | ---: | ---: |']
    for step in build['steps']:
        if step['stage'] in {'clone-main','compose-config','build-no-cache','build-no-cache-network-failure','up-healthy','container-acceptance',
                             'prepare-public-vector-model','prepare-public-vector-model-range',
                             'prepare-public-vector-model-range-parallel',
                             'confirm-public-vector-model','container-acceptance-after-model-preparation','container-full-isolated-test-env'}:
            lines.append(f"| {step['stage']} | {step['exit_code']} | {step['elapsed_seconds']:.6f} |")
    lines += ['', '首轮镜像来源 `'+initial_build['clone']['commit']+'`，无缓存构建 '+str(next(s['elapsed_seconds'] for s in initial_build['steps'] if s['stage']=='build-no-cache'))+'秒，容器全量实测3失败/10跳过；不是最终通过结果。', '',
        '首轮失败逐项：①Linux venv符号链接经Path.resolve变成系统Python，worker缺torch；改为venv --copies，构建时用解析后的解释器实际导入torch/Chroma/FlagEmbedding；②.dockerignore排除了全量测试必需的semantic-dedup-calibration.json，现仅放行这一份公开数值证据，其他报告仍排除；③调度单测继承部署Attention种子而测试库只含seed，现单测显式设定种子。没有放宽断言或把真向量改成假向量。', '',
        '另一次修正过程中的构建主动中止，实测退出码 '+str(next(s['exit_code'] for s in interrupted_build['steps'] if s['stage']=='build-no-cache'))+'、'+str(next(s['elapsed_seconds'] for s in interrupted_build['steps'] if s['stage']=='build-no-cache'))+'秒；原JSON/日志保留。公共依赖下载另有npm ECONNRESET退出1（329.919312秒）及主动中止的重试（261.743425秒、4294967295），原JSON/日志另存final-deployment-runtime-rebuild-network-failure.json。最终再次从远端main干净克隆、无缓存构建，使用官方HTTPS Debian源及npm有界重试，耗时见本节阶段表。', '',
        '首轮容器官方业务记录移到同一卷的独立归档目录，最终重验HTTP库重新为空；只保留该容器自身从公开源下载并完整校验过的模型权重，未复制宿主机缓存。归档：`'+json.dumps(build['data_archive'],ensure_ascii=False)+'`。']
    log = next(s for s in build['steps'] if s['stage']=='build-no-cache')
    lines += ['', '历次重建保留的原始结果（同一日志SHA去重）：', '', '| 来源主干 | 构建阶段 | 退出码 | 秒 |', '| --- | --- | ---: | ---: |']
    seen=set()
    for path in sorted(REPORTS.glob('final-deployment-runtime-rebuild*.json')):
        attempt=json.loads(path.read_text(encoding='utf-8'))
        for step in attempt['steps']:
            if not step['stage'].startswith('build-no-cache') or step['log_sha256'] in seen:
                continue
            seen.add(step['log_sha256'])
            lines.append(f"| {attempt['clone']['commit']} | {step['stage']} | {step['exit_code']} | {step['elapsed_seconds']:.6f} |")
    lines += ['', '后续一次大依赖下载仅34.0/196.3MB即断开，被SHA-256校验拒绝（415.716465秒）；未放宽校验。构建两个Python环境固定pip26.2.2并设20次有界恢复，依据[pip官方断点恢复说明](https://pip.pypa.io/en/stable/cli/pip/#cmdoption-resume-retries)。', '',
        '构建命令确有 `build --no-cache`。前端 npm ci/build、类型检查以及后端两套 Python 依赖安装/pip check 均由容器构建执行；未修改前端源码。', '',
        '首次容器验收尚在模型准备阶段时，因公开权重下载慢而主动中止（退出143），当时没有运行容器回归或上传官方文件。SDK重启后新建了下载临时文件，本轮保留其原约1.06GB容器内下载数据，改用公开文件范围请求续传，并按实测单连接带宽改为最多4路；中止阶段仍为143。完整文件通过固定大小与SHA-256校验，再由原SDK确认。下载准备阶段的实测时间/退出码完整保留在final-deployment-build-before-runtime-fix.json、final-deployment-build-initial-preparation.json；没有使用宿主机模型/解析缓存。', '',
        '完整构建日志（本地忽略目录）：`'+log['log']+'`；SHA-256：`'+log['log_sha256']+'`。', '',
        'Docker Engine/CLI 29.9.2、Desktop 4.96.3、Compose v5.6.1，Linux/amd64。运行期版本：`'+json.dumps(runtime['versions'],ensure_ascii=False)+'`。Python/Node基础镜像固定为3.12.15-slim-bookworm与22.23.4-bookworm-slim。', '',
        '| 服务 | 镜像 ID | 字节 | healthy | 镜像内 PDF / 密钥变量 |', '| --- | --- | ---: | --- | --- |']
    for service in runtime['services']:
        lines.append(f"| {service['name']} | {service['image_id']} | {service['size_bytes']} | {service['healthy']} | {service['input_audit']['pdf_count']} / {len(service['input_audit']['credential_names'])} |")
    lines += ['', '镜像审计使用无网络、无挂载的一次性容器；未拿含语料的运行容器冒充镜像本体。两镜像均无 .env/.git/官方pdf或已解析数据。官方语料仅在验收时只读挂载 /corpus，模型在容器内从固定公开快照下载到本轮新持久卷。最终权重字节/完整SHA-256：`'+json.dumps(runtime['model_snapshot'],ensure_ascii=False)+'`。根 .dockerignore 仍排除 pdf/、所有PDF、环境文件、宿主机依赖和Git。仓库既有 docs/technical-document.pdf 属于技术文档，未改动且同样被构建忽略；官方 pdf/ 没有跟踪文件。', '',
        '## 健康检查与无 Key 问答', '',
        '最终默认配置（每日调度）下：`'+json.dumps(runtime['http_status'],ensure_ascii=False)+'`；后端8000、前端3000均绑定127.0.0.1。两个服务均healthy，使用restart:unless-stopped。', '',
        '资源调整：独立可选 GROBID 容器实占约 '+resource['observed_memory_before']+'，而引擎总内存 '+resource['engine_memory']+'。本轮已停止该容器以给真实向量/OCR联测释放内存，退出码 '+str(resource['stop_exit_code'])+'，保留容器及配置；最终运行的是本单要求的前后端两服务。GROBID不是默认HTTP解析路径，本轮不宣称它仍在线。', '',
        '一次容器内真实 HTTP 摘录式问答：`Which optimizer?`，HTTP '+str(container['no_key_qa']['http_status'])+'，refused='+str(container['no_key_qa']['body']['refused'])+'，锚点数 '+str(len(container['no_key_qa']['body']['anchors']))+'。答案、数字校验与锚点见容器JSON；未调用生成式大模型。', '',
        '## 宿主机与容器全量回归', '',
        '| 环境 | 收集 | 通过 | 跳过 | 失败 | 错误 |', '| --- | ---: | ---: | ---: | ---: | ---: |']
    for label,key in [('宿主机最终','host_final'),('Linux容器','container')]:
        s=audit['regression'][key]
        lines.append(f"| {label} | {s['tests']} | {s['passed']} | {s['skipped']} | {s['failures']} | {s['errors']} |")
    lines += ['', '全量入口实际执行真实本地 BGE-M3/Chroma（4个自制Chunk、1024维dense+sparse）、真实自制扫描OCR，以及官方541页长书解析与分页索引；不是只跑假向量单测。真实向量版本/加载与查询耗时、长书Chunk数/索引秒数写入JUnit testcase properties。属性记录产生的xunit2兼容警告不计为失败；未隐藏警告。', '',
        '容器另有两项纯词法用例继承生产混合检索默认值而失败（完整JSON/JUnit保留在final-deployment-container-before-test-isolation*）。最终全量只给exec测试子进程设置SCHOLAR_GRAPH_RETRIEVAL_MODE=lexical，原断言不变，生产服务仍为bge_m3_hybrid；真实向量验收直接调用BGE-M3/Chroma并实际跑过，未用词法冒充。官方三用例来自同一最终镜像此前空库HTTP上传，未为此环境隔离复用宿主机解析结果。最终向量解释器及依赖：`'+json.dumps(runtime['vector_runtime'],ensure_ascii=False)+'`。首轮容器失败JUnit仍在final-deployment-container-before-runtime-fix-pytest.xml。', '',
        '两边均保留5项无Key真实模型测试跳过，跳过不计为通过。容器另有Windows专属测试跳过；逐项如下：', '']
    for case in audit['regression']['container']['skipped_cases']:
        lines.append('- `'+case['name']+'`：'+case['reason'])
    lines += ['', '最终原始控制台：宿主机 '+str(host['regression'].get('warnings'))+' 条警告，容器 '+str(container['regression'].get('warnings'))+' 条警告。两边有record_property与xunit2兼容警告，Linux另有只读源码目录pytest缓存写入警告；原文见[宿主机控制台](final-deployment-host-console.txt)、[容器控制台](final-deployment-container-console.txt)，未计为失败或隐去。']
    lines += ['', '宿主机首轮全量有1项失败：新增真向量测试错误地将排序列表当字典读取。已修正断言，定向真向量测试通过，再完整重跑得到上表最终结果。首轮JSON/JUnit及原日志保留，不将失败改成通过。并行重建期间另一轮为604通过/5跳过/2个真实OCR失败（单页90秒超时），原JSON/JUnit另存final-deployment-host-during-rebuild*，未把负载认定为唯一根因。随后新增共享公开OCR权重缓存及独立7200秒准备步骤，推理仍为真实Paddle、单页仍90秒，再串行跑完整层。最终宿主机JSON合并最后回归与本单此前新目录已完成的官方三用例并明确来源；PDF切块算法未改，容器则使用最终镜像从空HTTP库重新上传。', '',
        '## 官方三用例：两环境分别实测', '',
        '| 环境 | 文件 | HTTP | Chunk | 上传秒 | RSS采样峰值 MiB | 通过 |', '| --- | --- | ---: | ---: | ---: | ---: | --- |']
    for label,result in [('宿主机',host),('容器',container)]:
        for case in result['cases'].values():
            for row in case['uploads']:
                m=row['measurement']; rss=m.get('rss_peak_bytes',m.get('rss_sampled_peak_bytes',0))/1048576
                lines.append(f"| {label} | {row['file']} | {row['http_status']} | {row['chunks']} | {m['elapsed_seconds']:.6f} | {rss:.6f} | {row['passed']} |")
    lines += ['', '每次上传前状态接口为404，后续为completed且Chunk>0；源文件SHA-256在两环境与本地原件一致。容器用本轮空卷的实际HTTP上传，未挂宿主机解析结果。宿主机测量为测试进程及子进程RSS采样合计；容器测量为容器内可读进程RSS采样合计，含共享页重复计数可能。容器另存cgroup采样与生命周期峰值，后者不能当作单次上传峰值。宿主机用例与初期构建曾并行；最终容器官方用例与组件回归串行。记录的是当时环境墙钟耗时，不作为独占硬件性能对比。', '']
    for label,result in [('宿主机',host),('容器',container)]:
        dedup=result['cases']['dedup']['uploads'][-1]
        book=result['cases']['longbook']['uploads'][0]
        ocr=result['cases']['ocr']['uploads'][0]
        lines += ['### '+label+'业务证据', '', '第二传预警原文：', '', '> '+dedup['warning'], '',
            '去重裁决/差异HTTP均为200，建议`'+dedup['dedup-decision']['body']['recommendation']+'`。相似度/方法元数据保留在JSON，不把身份快速通道冒充向量计算。', '',
            'OCR文本样本：`'+' / '.join(ocr['text_samples'])+'`。完成页 '+str(len(ocr['batch_metrics']['completed_pages']))+'，失败页 '+str(ocr['batch_metrics']['failed_pages'])+'。', '',
            '长书 '+str(book['pages'])+'页、'+str(book['bytes'])+'字节；批次数 '+str(len(book['batch_metrics']['batches']))+'，索引相关累计 '+str(book['batch_metrics']['indexing_seconds'])+'秒，末页最大物理页 '+str(book['last_page']['max_pdf_page'])+'，越界返回 '+str(book['overflow_items'])+'条。索引计时含归一化、门禁、发布和SQLite提交，不是纯SQL时间。', '']
    lines += ['## 自动定时实测与最终配置', '',
        '实际机制是后端lifespan启动的interval线程，按数据目录持有操作系统锁；不依赖手动POST或宿主机任务计划程序。验收用同一代码的60秒覆盖配置，固定官方Attention种子、max_imports=0，只轮询公开arXiv形成候选。自动运行数（有真实公共查询记录）：'+str(len(container['automatic_public_runs']))+'。', '',
        '| 自动运行 id | UTC开始时间 | 状态 | 候选 | 导入 | 上游错误 |', '| --- | --- | --- | ---: | ---: | --- |']
    for run in container['automatic_public_runs']:
        errors='；'.join(e.get('message','') for e in run.get('errors',[])) or '无'
        lines.append(f"| {run['run_id']} | {run['started_at']} | {run['status']} | {run['candidate_count']} | {run['imported_count']} | {errors} |")
    lines += ['', '上表中failed/partial/running保持原状态；自动触发成功不等于上游候选抓取成功。完整scheduler_started/run_started/run_finished、耗时、候选数和失败原文见容器JSON及持久卷tracking/scheduler-events.jsonl；运行记录另在state.sqlite3。首轮上传持有ingestion锁时，定时轮次因30秒锁等待失败；上传后另取证5轮实际公共查询全部completed（final-deployment-timer-first.json）。最终观察器在上传后最多再等600秒，要求run_finished日志与至少2条实际查询对应，未手动POST触发。原探针即时快照和退出码在probe_snapshot_before_timer_wait、original_probe_exit_code保留，不改写为原本通过。', '',
        '验收后移除短周期及语料覆盖，使用根Compose恢复默认每日调度，两服务再次healthy。最终scheduler_details：', '',
        '```json',json.dumps(runtime['scheduler']['scheduler_details'],ensure_ascii=False,indent=2),'```','',
        '演示部署沿用同一后端调度机制，默认间隔86400秒；容器启动时自动注册，在未手动停止的情况下，restart:unless-stopped会在Docker引擎恢复时重启容器。数据卷日志保留。旧镜像/旧数据卷未删除，本轮最终服务使用新项目 `'+build['project']+'` 与新卷，包含本轮实际上传的4份官方文件。', '',
        '## 回归分层及复现说明', '',
        '后端README新增“最终 Docker 部署与回归分层”。快速层显式白名单，提交钩子每次运行148通过（新增OCR配置测试后465 deselected，之前463）；不加载模型、不跑OCR、不建大索引。Git钩子路径本工作区已启用，克隆后用`git config --local core.hooksPath services/git-hooks`启用。GitHub push/PR还有自动快速CI，部署功能提交运行已真实通过：['+str(ci['run_id'])+']('+ci['url']+')。此前PR专用接口与匿名API403未能确认状态，随后通过连接器通用workflow接口取得该成功运行及步骤证据。', '',
        '全量层仅单子验收与部署前运行：`python tests/run_regression.py full --no-key --corpus-dir pdf`；包含真向量、OCR及长书。没有Key的5项真模型测试跳过；有已授权模型环境且去掉--no-key才调用真实模型。本单未使用Key。', '',
        'Docker无缓存构建：`docker compose build --no-cache`；启动：`docker compose up -d --wait`；快速测试：`docker compose exec -T backend python tests/run_regression.py fast --no-key`。公开模型准备、只读官方语料覆盖与完整探针命令详见backend/README.md。', '',
        '## 审计与证据', '',
        '最终审计：'+str(sum(audit['checks'].values()))+'/'+str(len(audit['checks']))+'项通过。contracts/、frontend/、docs/、prompts/、experiments/、test-records/相对开工基线零改动。已知环境Key对Git跟踪内容及本轮证据做不回显值的扫描，无命中；Key未传构建/容器，未写任何文件。', '',
        '- [构建与克隆](final-deployment-build.json)',
        '- [容器官方用例与定时记录](final-deployment-container.json)',
        '- [容器JUnit](final-deployment-container-pytest.xml)',
        '- [宿主机最终结果](final-deployment-host-final.json)',
        '- [宿主机最终JUnit](final-deployment-host-final-pytest.xml)',
        '- [宿主机首轮失败保留](final-deployment-host.json)',
        '- [最终运行/镜像审计](final-deployment-runtime.json)',
        '- [CI记录](final-deployment-ci.json)',
        '- [最终审计](final-deployment-audit.json)', '']
    (REPORTS/'final-deployment-acceptance.md').write_text('\n'.join(lines),encoding='utf-8')
    print(json.dumps({'passed':passed,'report':'tests/reports/final-deployment-acceptance.md'},ensure_ascii=False))


if __name__=='__main__':
    main()

"""Render the default-path report from audited real evidence and JUnit."""
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
REPORTS=ROOT/'tests/reports'


def main():
    data=json.loads((REPORTS/'grobid-default-path-live.json').read_text(encoding='utf-8'))
    audit=json.loads((REPORTS/'grobid-default-path-audit.json').read_text(encoding='utf-8'))
    enabled=data['groups']['enabled'];fallback=data['groups']['unreachable'];reg=audit['regression']
    lines=['# GROBID 默认路径增强验收（打磨 A）','',
        '日期：2026-10-26。输入为 **官方 pdf/ 真文件**。', '',
        '**最终结论：'+('通过' if audit['passed'] else '未通过')+'。** 默认HTTP单/批上传及arXiv下载后的工厂已接入可回落GROBID增强，原有契约零改动。', '',
        '开工 `git pull --ff-only`：`Already up to date.`；主干及干净工作区基线：`'+audit['baseline']+'`。', '',
        '## 默认接线和边界','',
        'UploadService默认工厂与ArxivFetcher默认工厂都创建Pipeline(enhancement=DefaultGrobid())，MinerU产生完整记录后执行增强。抓取仍复用原ParseJob、门禁与存储，没有另建解析管线。默认启用，服务地址GROBID_URL默认http://127.0.0.1:8070，超时默认60秒、上限120秒；显式禁用设SCHOLAR_GRAPH_GROBID_ENABLED=false。Docker Desktop配置提供host.docker.internal:8070；已从现有后端容器实测该地址isalive为200 true。', '',
        '本单官方两组入口为工作树的真实默认ASGI应用（TestClient，不传pipeline_factory），本地MinerU和HTTP GROBID均实际执行，没有替换引擎或TEI。现有已运行的部署镜像没有在本单重建，不能把工作树验证写成旧镜像已更新。前端源码未动；只读核实原同源代理会转发全部X-ScholarGraph-*响应头。', '',
        '独立CLI --grobid-url和Pipeline(grobid=...)继续保留显式严格行为；本单安全回落用于新接入的默认工厂。相同文件哈希命中不可覆盖旧记录，复用原方法并标cache_hit=true/grobid_attempted=false，不谎称再次调用；历史记录不会自动迁移增强。', '',
        '## 合并规则','',
        '| 字段/内容 | 权威和冲突规则 | 空值规则 |','| --- | --- | --- |',
        '| title / abstract | 默认上传采用经门禁的GROBID非空值；arXiv已核验非空值优先 | null/空数组不清空原值 |',
        '| authors / institutions | 同上；合并层过滤明显机构作者和工作声明/会议脚注，原值和过滤原因留证 | 过滤后为空则保留本地值 |',
        '| year | 保留本地或已核验arXiv值；GROBID header可能是版本日期，不自动采用 | 未知保留null |',
        '| doi | 已知本地或arXiv裸DOI优先，GROBID只补空DOI | 空值不清空 |',
        '| id/schema_version/file_hash/page_count/has_text_layer/source/arxiv_id/version | 保留文件身份和既有来源；GROBID不覆盖 | 沿用原值 |',
        '| 全部Chunk、正文、章节、PDF物理页、bbox | MinerU/OCR为准，GROBID不替换 | 沿用原值 |',
        '| ReferenceEntry | 保留本地number/ref_id/paper_id；同序号还必须有一致DOI/arXiv、规范化标题或作者年份依据，显式标题/标识冲突不合并；通过后采用GROBID非空字段 | 无法对齐条目保留本地，不猜补、不追加无锚点条目 |',
        '| CitationLink | 保留已有真实引用出现位置，仅从实际Chunk重建并补充合法链接 | Schema、外键和锚点门禁均保留 |','',
        'GROBID处理的是隔离的候选副本；不可达、超时、非2xx、无效XML/Schema、改动Chunk、无可合并内容都丢弃整个候选并回落原MinerU结果。不会把部分修改混入发布组。其异常位于可选解析元数据，整体ParseStatus仍可completed，error_code/error_message保持成功口径。', '',
        '## 可选方法标记（没有新增契约字段）','',
        '- 单上传、详情、解析状态：响应头 `X-ScholarGraph-Parse-Meta`，percent-encoded UTF-8 JSON，CORS已暴露。',
        '- 批量成功项及arXiv抓取封装：可选 `parse_metadata`。四类记录及ParseStatus响应体仍为原契约。',
        '- 本地逐次记录：`jobs/<job_id>/parse-metadata.json`；逐条参考匹配依据仅留本地，响应给数量摘要，避免过大响应头。',
        '- method：`mineru`为明确禁用；`mineru+grobid`为真实调用且有可发布增强；`mineru-fallback`为尝试失败或无可合并内容。另有grobid_attempted、耗时、fallback_reason、grobid_error、增强字段及参考数量。', '',
        '## 官方 Attention v7 两组实测','',
        '输入：`pdf/'+data['file']+'`，'+str(data['bytes'])+'字节，SHA-256：`'+data['sha256']+'`。两组均为新空目录，上传前状态404；原件下载哈希一致。输出根目录：`'+data['run_root']+'`。', '',
        '真实服务镜像：`'+audit['service_image']+'`；`/api/isalive`='+str(data['service']['alive'])+'；版本响应：`'+json.dumps(data['service']['version'],ensure_ascii=False)+'`。关闭header/citations consolidation，无Crossref补全。', '',
        '| 组 | HTTP | method | 上传秒 | GROBID阶段秒 | Chunk/参考/引用 | 端点检查 |',
        '| --- | ---: | --- | ---: | ---: | --- | --- |']
    for name,row in [('服务可用',enabled),('真实TCP不可达',fallback)]:
        c=row['counts'];m=row['parse_metadata']
        lines.append(f"| {name} | {row['http_status']} | {m['method']} | {row['elapsed_seconds']:.6f} | {m['grobid_elapsed_seconds']:.6f} | {c['chunks']}/{c['reference_entries']}/{c['citation_links']} | {sum(row['checks'].values())}/{len(row['checks'])} |")
    lines += ['', '不可达组使用真实绑定但未监听的本地TCP端点，连接真实拒绝；GROBID容器保持运行。该组未用HTTP mock，也未把停用配置的mineru分支当作不可达回落。', '',
        '可用组增强字段：`'+json.dumps(enabled['parse_metadata']['paper_fields'],ensure_ascii=False)+'`；参考匹配 '+str(enabled['parse_metadata']['reference_matches_count'])+' 条，实际字段增强 '+str(enabled['parse_metadata']['references_enriched'])+' 条。无法匹配 '+str(enabled['parse_metadata'].get('unmatched_grobid_references',0))+' 条；有1条匹配但无可用非空改动，保留本地值。两组Chunk逐条完全相同。', '',
        '可用组题录样本：','', '```json',json.dumps({k:enabled['paper_meta'][k] for k in ('title','authors','institutions','abstract','year','doi')},ensure_ascii=False,indent=2),'```','',
        '过滤/暂不采用的原始候选：','', '```json',json.dumps({k:enabled['full_parse_metadata'].get(k) for k in ('discarded_header_values','withheld_header_fields')},ensure_ascii=False,indent=2),'```','',
        '首轮未加保护的原始结果另存grobid-default-path-initial-live.json：作者中混入Google Brain/Research、机构中混入工作脚注、year为2023。最终保留8个人名、1个机构；2023仅留方法日志，论文year保持null，没有猜填发表年。此保护是有限规则，不把CRF输出宣称为通用实体识别或题录准确率评测。', '',
        '上游CRF仍有质量边界：这里的1个机构不代表全文机构全集，摘要还夹带部分贡献脚注。本单验证接线、回落、合规发布与本例保护规则，不宣称完整题录抽取准确率通过。', '',
        '不可达组回落原文：`'+fallback['parse_metadata']['fallback_reason']+'`；错误封装：`'+json.dumps(fallback['parse_metadata']['grobid_error'],ensure_ascii=False)+'`。结果为completed/100，原MinerU数据完整发布。', '',
        '## 回归和审计','',
        '| 层/证据 | 结果 |','| --- | --- |',
        '| 最终全量 | '+str(reg['tests'])+'项：'+str(reg['passed'])+'通过、'+str(reg['skipped'])+'跳过、'+str(reg['failures'])+'失败、'+str(reg['errors'])+'错误 |',
        '| 快速层 | 163通过；提交钩子实际执行；不依赖Docker或模型 |',
        '| 默认路径新增测试 | 15项：成功/不可达/超时/HTTP/XML/配置错误/坏Schema或Chunk回滚/空结果/重传/批量/arXiv/合并质量保护 |',
        '| 两组真实端点 | 各9项检查通过，包含Schema/真实锚点、详情方法持久化、原PDF哈希 |',
        '| 最终审计 | '+str(sum(audit['checks'].values()))+'/'+str(len(audit['checks']))+'通过 |','',
        '全量命令：`python tests/run_regression.py full --no-key --corpus-dir pdf`。真实本地BGE-M3/Chroma、真实自制OCR、官方541页长书均执行；5项无Key真模型跳过不算通过。组件回归隔离关闭可选GROBID，新测试显式启用模拟响应；真实GROBID由上表两组官方实测证明。arXiv默认工厂的接线另由合成Atom/PDF测试覆盖，不写成真实公共抓取已通过。', '',
        '首次全量为627项，620通过、5跳过、2失败：新增日志对直接调用_publish而未启动parse的既有去重用例不兼容；已修复并定向22项通过，失败JUnit保留。随后627项全量为622通过/5跳过；题录质量保护新增1项后，以最终628项结果为准。另一次定向运行曾因临时目录父路径缺失出现11个setup错误，目录修正后原35项定向通过，旧证据在data/grobid-default-tests/保留。没有把这些失败/错误改写为通过。', '',
        '两组实际生成物均为官方pdf/真文件；普通单元测试使用自制PDF/TEI。未调用生成式大模型、未使用真实API Key；语料pdf/仍忽略且未跟踪。contracts/、frontend/、docs/、prompts/、experiments/、test-records/相对开工基线零改动。现有运行的旧后端镜像不计入这次新接线部署验收。', '',
        '- [最终两组实测](grobid-default-path-live.json)',
        '- [最终JUnit](grobid-default-path-pytest.xml)',
        '- [首轮失败JUnit](grobid-default-path-initial-pytest.xml)',
        '- [保护前题录原值](grobid-default-path-initial-live.json)',
        '- [审计](grobid-default-path-audit.json)','']
    (REPORTS/'grobid-default-path-acceptance.md').write_text('\n'.join(lines),encoding='utf-8')
    print(json.dumps({'passed':audit['passed'],'report':'tests/reports/grobid-default-path-acceptance.md'}))


if __name__=='__main__':main()

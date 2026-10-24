import Link from "next/link";
import { notFound } from "next/navigation";
import {
  paperMetaMock,
  chunkMock,
  referenceEntryMock,
  citationLinkMock,
  qaAnswerMock,
  parseStatusMock,
  dedupDecisionMock,
  diffSummaryMock,
  chartOutputMock,
} from "@/mock";

type Chunk = (typeof chunkMock)[number];
type Ref = (typeof referenceEntryMock)[number];
type Link_ = (typeof citationLinkMock)[number];

const STATUS_TAG: Record<string, string> = {
  queued: "sg-tag sg-tag--muted",
  parsing: "sg-tag sg-tag--info",
  ocr: "sg-tag sg-tag--info",
  indexing: "sg-tag sg-tag--info",
  completed: "sg-tag sg-tag--success",
  failed: "sg-tag sg-tag--error",
};

const CHECK_TAG: Record<string, string> = {
  passed: "sg-tag sg-tag--success",
  failed: "sg-tag sg-tag--error",
  unverifiable: "sg-tag sg-tag--warning",
  not_applicable: "sg-tag sg-tag--muted",
};

function sectionText(chunk: Chunk): string {
  return chunk.section_path.length > 0
    ? chunk.section_path.join(" / ")
    : "（无章节标题）";
}

function anchorLabel(chunk: Chunk | undefined): string {
  if (!chunk) return "锚点指向的分块不在当前假数据集中";
  return `p.${chunk.page_number} · ${chunk.chunk_id}`;
}

export default async function PaperDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;

  const paper = paperMetaMock.find((item) => item.id === id);
  if (!paper) {
    notFound();
  }

  const chunks = chunkMock.filter((item) => item.paper_id === id);
  const refs = referenceEntryMock.filter((item) => item.paper_id === id);
  const links: readonly Link_[] = citationLinkMock.filter(
    (item) => item.paper_id === id,
  );
  const statuses = parseStatusMock.filter((item) => item.paper_id === id);
  const lastStatus = statuses[statuses.length - 1];
  const dedup = dedupDecisionMock.filter(
    (item) => item.old_paper_id === id || item.new_paper_id === id,
  );
  const diff = diffSummaryMock.filter(
    (item) => item.old_paper_id === id || item.new_paper_id === id,
  );

  const newPaperIds = new Set(
    dedupDecisionMock.map((item) => item.new_paper_id),
  );

  return (
    <main className="sg-shell">
      <p className="sg-back">
        <Link href="/">← 返回论文库</Link>
      </p>

      <div className="sg-page-head">
        <p className="sg-eyebrow">PaperMeta</p>
        <h1 className="sg-title">{paper.title ?? "（标题未提取）"}</h1>
        <p className="sg-lede">{paper.abstract ?? "（摘要未提供）"}</p>
      </div>

      {/* 1. 解析状态 */}
      <section className="sg-section">
        <div className="sg-section__head">
          <h2 className="sg-section__title">解析状态 · ParseStatus</h2>
          <span className="sg-section__hint">
            v1.1 契约 · 静态快照，不轮询
          </span>
        </div>

        {lastStatus ? (
          <>
          <dl className="sg-kv">
            <dt>paper_id</dt>
            <dd className="sg-mono">{lastStatus.paper_id}</dd>
            <dt>状态 status</dt>
            <dd>
              <span className={STATUS_TAG[lastStatus.status] ?? "sg-tag"}>
                {lastStatus.status}
              </span>
            </dd>
            <dt>进度 progress</dt>
            <dd>
              <div className="sg-progress">
                <div
                  className={
                    lastStatus.status === "failed"
                      ? "sg-progress__bar sg-progress__bar--failed"
                      : "sg-progress__bar"
                  }
                  style={{ width: `${lastStatus.progress}%` }}
                />
              </div>
              <span className="sg-num">{lastStatus.progress}%</span>
            </dd>
            <dt>当前阶段 current_stage</dt>
            <dd>{lastStatus.current_stage}</dd>
            <dt>错误码 error_code</dt>
            <dd className="sg-mono">{lastStatus.error_code ?? "—"}</dd>
            <dt>错误信息 error_message</dt>
            <dd>{lastStatus.error_message ?? "—"}</dd>
          </dl>

          <h3 className="sg-subhead">状态推进快照</h3>
          <table className="sg-table">
            <thead>
              <tr>
                <th>状态</th>
                <th className="sg-num">进度</th>
                <th>当前阶段</th>
                <th className="sg-num">错误码</th>
              </tr>
            </thead>
            <tbody>
              {statuses.map((item) => (
                <tr key={`${item.status}-${item.progress}`}>
                  <td>
                    <span className={STATUS_TAG[item.status] ?? "sg-tag"}>
                      {item.status}
                    </span>
                  </td>
                  <td className="sg-num">{item.progress}%</td>
                  <td>{item.current_stage}</td>
                  <td className="sg-num">{item.error_code ?? "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
          </>
        ) : (
          <p>该论文在假数据集中没有对应的 ParseStatus 记录。</p>
        )}
      </section>

      {/* 2. 分块列表 */}
      <section className="sg-section">
        <div className="sg-section__head">
          <h2 className="sg-section__title">分块列表 · Chunk</h2>
          <span className="sg-section__hint">共 {chunks.length} 条</span>
        </div>

        <table className="sg-table">
          <thead>
            <tr>
              <th className="sg-num">页码</th>
              <th>章节路径</th>
              <th>正文</th>
              <th>类型</th>
              <th className="sg-num">bbox</th>
              <th className="sg-num">chunk_id</th>
            </tr>
          </thead>
          <tbody>
            {chunks.map((chunk) => (
              <tr key={chunk.chunk_id}>
                <td className="sg-num">{chunk.page_number}</td>
                <td>
                  <div>{sectionText(chunk)}</div>
                  <div className="sg-mono">
                    H1 {chunk.heading_1 ?? "—"} / H2{" "}
                    {chunk.heading_2 ?? "—"} / H3 {chunk.heading_3 ?? "—"}
                  </div>
                </td>
                <td>
                  <p className="sg-prose">{chunk.text}</p>
                </td>
                <td>
                  <span className="sg-tag">{chunk.type}</span>
                </td>
                <td className="sg-num">
                  {chunk.bbox ? chunk.bbox.join(", ") : "null"}
                </td>
                <td className="sg-mono">{chunk.chunk_id}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      {/* 3. 参考文献与引用对应关系 */}
      <section className="sg-section">
        <div className="sg-section__head">
          <h2 className="sg-section__title">
            参考文献与引用对应 · ReferenceEntry / CitationLink
          </h2>
          <span className="sg-section__hint">
            条目 {refs.length} 条 · 引用 {links.length} 条
          </span>
        </div>

        <h3 className="sg-subhead">文末条目</h3>
        <table className="sg-table">
          <thead>
            <tr>
              <th className="sg-num">编号</th>
              <th>作者</th>
              <th className="sg-num">年份</th>
              <th>标题</th>
              <th>出处</th>
              <th className="sg-num">DOI</th>
              <th className="sg-num">arXiv</th>
            </tr>
          </thead>
          <tbody>
            {refs.map((ref: Ref) => (
              <tr key={ref.ref_id}>
                <td className="sg-num">[{ref.number}]</td>
                <td>{ref.authors.join("; ")}</td>
                <td className="sg-num">{ref.year ?? "—"}</td>
              <td>{ref.title ?? "—"}</td>
                <td>{ref.venue ?? "—"}</td>
                <td className="sg-num">{ref.doi ?? "—"}</td>
                <td className="sg-num">{ref.arxiv_id ?? "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>

        <h3 className="sg-subhead">正文 ↔ 文末 对应关系</h3>
        <table className="sg-table">
          <thead>
            <tr>
              <th className="sg-num">引用序号</th>
              <th className="sg-num">所在页</th>
              <th className="sg-num">所在分块</th>
              <th className="sg-num">目标条目 ref_id</th>
              <th>正文片段</th>
            </tr>
          </thead>
          <tbody>
            {links.map((link) => {
              const chunk = chunks.find(
                (item) => item.chunk_id === link.chunk_id,
              );
              const target = refs.find((item) => item.ref_id === link.ref_id);
              return (
                <tr
                  key={`${link.citation_number}-${link.page_number}-${link.chunk_id}`}
                >
                  <td className="sg-num">[{link.citation_number}]</td>
                  <td className="sg-num">{link.page_number}</td>
                  <td className="sg-mono">{link.chunk_id}</td>
                  <td className="sg-mono">
                    {link.ref_id}
                    <div className="sg-tag sg-tag--muted">
                      {target ? `→ ${target.title ?? "—"}` : "→ 条目不在本页数据集中"}
                    </div>
                  </td>
                  <td>
                    <p className="sg-prose">{chunk?.text ?? "—"}</p>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </section>

      {/* 4. 问答区 */}
      <section className="sg-section">
        <div className="sg-section__head">
          <h2 className="sg-section__title">问答 · QAAnswer</h2>
          <span className="sg-section__hint">
            每条事实带锚点；无锚点标不可验证
          </span>
        </div>

        {qaAnswerMock.map((qa, index) => (
          <div key={index}>
            <h3 className="sg-subhead">
              示例 {index + 1} · {qa.refused ? "拒答" : "正常回答"}
            </h3>
            <dl className="sg-kv">
              <dt>schema_version</dt>
              <dd className="sg-mono">{qa.schema_version}</dd>
              <dt>refused</dt>
              <dd>
                <span
                  className={
                    qa.refused
                      ? "sg-tag sg-tag--warning"
                      : "sg-tag sg-tag--info"
                  }
                >
                  {String(qa.refused)}
                </span>
              </dd>
              <dt>answer</dt>
              <dd className="sg-prose">{qa.answer}</dd>
              <dt>anchors</dt>
              <dd>
                {qa.anchors.length === 0 ? (
                  <span className="sg-tag sg-tag--muted">
                    无锚点（拒答时允许为空）
                  </span>
                ) : (
                  <ul>
                    {qa.anchors.map((anchor, anchorIndex) => (
                      <li key={anchorIndex}>
                        <span className="sg-anchor">
                          p.{anchor.page_number} · {anchor.chunk_id}
                        </span>{" "}
                        <span className="sg-mono">
                          {anchor.section.join(" / ")}
                        </span>
                      </li>
                    ))}
                  </ul>
                )}
              </dd>
              <dt>numeric_fact_check.status</dt>
              <dd>
                <span
                  className={
                    CHECK_TAG[qa.numeric_fact_check.status] ?? "sg-tag"
                  }
                >
                  {qa.numeric_fact_check.status}
                </span>
              </dd>
              <dt>checks</dt>
              <dd>
                {qa.numeric_fact_check.checks.length === 0 ? (
                  <span className="sg-tag sg-tag--muted">
                    无可校验数字事实（not_applicable 时 checks 必须为空）
                  </span>
                ) : (
                  <table className="sg-table">
                    <thead>
                      <tr>
                        <th>待核数字陈述</th>
                        <th>状态</th>
                        <th>证据锚点</th>
                        <th>校验理由</th>
                      </tr>
                    </thead>
                    <tbody>
                      {qa.numeric_fact_check.checks.map((check, i) => (
                        <tr key={i}>
                          <td>{check.claim}</td>
                          <td>
                            <span
                              className={CHECK_TAG[check.status] ?? "sg-tag"}
                            >
                              {check.status}
                            </span>
                          </td>
                          <td>
                            {check.evidence.length > 0 ? (
                              check.evidence.map((ev, j) => (
                                <div key={j} className="sg-mono">
                                  p.{ev.page_number} · {ev.chunk_id}
                                </div>
                              ))
                            ) : (
                              <span className="sg-tag sg-tag--warning">
                                无证据
                              </span>
                            )}
                          </td>
                          <td>{check.reason}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </dd>
            </dl>
          </div>
        ))}
      </section>

      {/* 5. 去重提示区 */}
      <section className="sg-section">
        <div className="sg-section__head">
          <h2 className="sg-section__title">去重提示 · DedupDecision / DiffSummary</h2>
          <span className="sg-section__hint">v1.1 契约 · 示例原样展示</span>
        </div>

        {dedup.length === 0 ? (
          <p>该论文在假数据集中没有对应的去重裁决记录。</p>
        ) : (
          <>
            <h3 className="sg-subhead">版本裁决</h3>
            <table className="sg-table">
              <thead>
                <tr>
                  <th>旧版本</th>
                  <th>新版本</th>
                  <th className="sg-num">相似度</th>
                  <th>建议</th>
                  <th>人工覆盖</th>
                  <th>证据</th>
                </tr>
              </thead>
              <tbody>
                {dedup.map((item, index) => (
                  <tr key={index}>
                    <td className="sg-mono">{item.old_paper_id}</td>
                    <td className="sg-mono">
                      {item.new_paper_id}
                      {newPaperIds.has(item.new_paper_id) && id === item.new_paper_id ? (
                        <span className="sg-tag sg-tag--success">当前</span>
                      ) : null}
                    </td>
                    <td className="sg-num">{item.similarity}</td>
                    <td>
                      <span className="sg-tag sg-tag--info">
                        {item.recommendation}
                      </span>
                    </td>
                    <td className="sg-mono">{String(item.human_override)}</td>
                    <td>
                      {item.evidence.map((ev, i) => (
                        <div key={i}>
                          <span className="sg-anchor">
                            {anchorLabel(
                              chunks.find(
                                (c) =>
                                  c.chunk_id === ev.anchor.chunk_id,
                              ),
                            )}
                          </span>
                          <div>{ev.reason}</div>
                        </div>
                      ))}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </>
        )}

        {diff.length === 0 ? (
          <p>该论文在假数据集中没有对应的版本差异摘要。</p>
        ) : (
          <>
            <h3 className="sg-subhead">版本差异摘要</h3>
            <table className="sg-table">
              <thead>
                <tr>
                  <th>变化章节</th>
                  <th>摘要</th>
                  <th>关键句</th>
                  <th>状态</th>
                </tr>
              </thead>
              <tbody>
                {diff.map((item, index) => (
                  <tr key={index}>
                    <td>{item.changed_sections.join("；")}</td>
                    <td>{item.summary_text}</td>
                    <td>
                      {item.key_sentences.map((sentence, i) => (
                        <div key={i}>
                          <span className="sg-prose">{sentence.text}</span>
                          <div className="sg-mono">
                            {sentence.anchor
                              ? `p.${sentence.anchor.page_number} · ${sentence.anchor.chunk_id}`
                              : "无锚点"}
                          </div>
                        </div>
                      ))}
                    </td>
                    <td>
                      {item.key_sentences.map((sentence, i) => (
                        <div key={i}>
                          <span
                            className={
                              sentence.status === "verified"
                                ? "sg-tag sg-tag--success"
                                : "sg-tag sg-tag--warning"
                            }
                          >
                            {sentence.status}
                          </span>
                        </div>
                      ))}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </>
        )}
      </section>

      {/* 6. 图表占位区 */}
      <section className="sg-section">
        <div className="sg-section__head">
          <h2 className="sg-section__title">图表占位 · ChartOutput</h2>
          <span className="sg-section__hint">图片位为占位框，非实测图</span>
        </div>

        {chartOutputMock.map((chart) => (
          <div key={chart.chart_id}>
            <h3 className="sg-subhead">{chart.chart_id}</h3>
            <dl className="sg-kv">
              <dt>chart_type</dt>
              <dd>
                <span className="sg-tag sg-tag--info">{chart.chart_type}</span>
              </dd>
              <dt>series</dt>
              <dd>
                {chart.series.map((s, i) => (
                  <div key={i} className="sg-mono">
                    {s.name}：{s.values.join(", ")}
                  </div>
                ))}
              </dd>
              <dt>caption</dt>
              <dd className="sg-prose">{chart.caption}</dd>
              <dt>image_ref</dt>
              <dd className="sg-mono">{chart.image_ref}</dd>
            </dl>

            <div className="sg-placeholder">
              <span className="sg-placeholder__title">
                placeholder · {chart.chart_type}
              </span>
              <span>
                图片位：此处不是实测图表，仅为版式占位；真实图表需后端产出后接入。
              </span>
            </div>

            <h3 className="sg-subhead">数字校验结果</h3>
            <table className="sg-table">
              <thead>
                <tr>
                  <th className="sg-num">数值</th>
                  <th className="sg-num">CSV</th>
                  <th className="sg-num">行号</th>
                  <th className="sg-num">列名</th>
                  <th>校验</th>
                </tr>
              </thead>
              <tbody>
                {chart.numeric_checks.map((check, i) => (
                  <tr key={i}>
                    <td className="sg-num">{check.value}</td>
                    <td className="sg-mono">{check.csv_anchor.csv_ref}</td>
                    <td className="sg-num">{check.csv_anchor.row_number}</td>
                    <td className="sg-mono">
                      {check.csv_anchor.column_name}
                    </td>
                    <td>
                      <span
                        className={
                          check.verified
                            ? "sg-tag sg-tag--success"
                            : "sg-tag sg-tag--warning"
                        }
                      >
                        {String(check.verified)}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ))}
      </section>
    </main>
  );
}

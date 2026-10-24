import Link from "next/link";
import {
  fetchChunks,
  fetchCitationLinks,
  fetchDedupDecision,
  fetchDiffSummary,
  fetchPaper,
  fetchParseStatus,
  fetchReferences,
} from "@/lib/api";
import type {
  Chunk,
  CitationLink,
  DedupDecision,
  DiffSummary,
  Paged,
  PaperMeta,
  ParseStatus,
  ReferenceEntry,
} from "@/lib/types";
import ErrorState from "@/components/ErrorState";
import ParseStatusLive from "@/components/ParseStatusLive";
import UnavailablePanel from "@/components/UnavailablePanel";

type Result<T> =
  | { kind: "ok"; value: T }
  | { kind: "error"; error: unknown };

async function settle<T>(promise: Promise<T>): Promise<Result<T>> {
  try {
    return { kind: "ok", value: await promise };
  } catch (error) {
    return { kind: "error", error };
  }
}

const STATUS_TAG: Record<string, string> = {
  queued: "sg-tag sg-tag--muted",
  parsing: "sg-tag sg-tag--info",
  ocr: "sg-tag sg-tag--info",
  indexing: "sg-tag sg-tag--info",
  completed: "sg-tag sg-tag--success",
  failed: "sg-tag sg-tag--error",
};

function sectionPathText(chunk: Chunk): string {
  return chunk.section_path.length > 0
    ? chunk.section_path.join(" / ")
    : "（无章节标题）";
}

export default async function PaperDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;

  const paperResult = await settle(fetchPaper(id));

  if (paperResult.kind === "error") {
    return (
      <main className="sg-shell">
        <p className="sg-back">
          <Link href="/">← 返回论文库</Link>
        </p>
        <div className="sg-page-head">
          <p className="sg-eyebrow">GET /api/v1/papers/{id}</p>
          <h1 className="sg-title">论文详情</h1>
        </div>
        <section className="sg-section">
          <div className="sg-section__head">
            <h2 className="sg-section__title">取数失败</h2>
            <span className="sg-section__hint">未取得该论文</span>
          </div>
          <ErrorState title="论文详情取数失败" error={paperResult.error} />
        </section>
      </main>
    );
  }

  const paper: PaperMeta = paperResult.value;

  const [chunksResult, refsResult, linksResult, statusResult, dedupResult, diffResult] =
    await Promise.all([
      settle<Paged<Chunk>>(fetchChunks(id)),
      settle<Paged<ReferenceEntry>>(fetchReferences(id)),
      settle<Paged<CitationLink>>(fetchCitationLinks(id)),
      settle<ParseStatus>(fetchParseStatus(id)),
      settle<DedupDecision | null>(fetchDedupDecision(id)),
      settle<DiffSummary | null>(fetchDiffSummary(id)),
    ]);

  const chunks = chunksResult.kind === "ok" ? chunksResult.value.items : [];
  const refs = refsResult.kind === "ok" ? refsResult.value.items : [];
  const links = linksResult.kind === "ok" ? linksResult.value.items : [];

  return (
    <main className="sg-shell">
      <p className="sg-back">
        <Link href="/">← 返回论文库</Link>
      </p>

      <div className="sg-page-head">
        <p className="sg-eyebrow">GET /api/v1/papers/{id}</p>
        <h1 className="sg-title">{paper.title ?? "（标题未提取）"}</h1>
        <p className="sg-lede">{paper.abstract ?? "（摘要未提供）"}</p>
      </div>

      {/* 解析状态：非终态时前端轮询，到达终态即停 */}
      <section className="sg-section">
        <div className="sg-section__head">
          <h2 className="sg-section__title">解析状态 · ParseStatus</h2>
          <span className="sg-section__hint">
            GET /papers/{id}/parse-status · 非终态轮询，终态停止
          </span>
        </div>
        {statusResult.kind === "ok" ? (
          <ParseStatusLive paperId={id} initial={statusResult.value} />
        ) : (
          <ErrorState title="解析状态取数失败" error={statusResult.error} />
        )}
      </section>

      {/* 分块 */}
      <section className="sg-section">
        <div className="sg-section__head">
          <h2 className="sg-section__title">分块列表 · Chunk</h2>
          <span className="sg-section__hint">
            GET /papers/{id}/chunks · 分页
          </span>
        </div>
        {chunksResult.kind === "error" ? (
          <ErrorState title="分块列表取数失败" error={chunksResult.error} />
        ) : chunksResult.value.items.length === 0 ? (
          <p>后端返回 0 条分块（total={chunksResult.value.total}）。</p>
        ) : (
          <>
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
                {chunksResult.value.items.map((chunk) => (
                  <tr key={chunk.chunk_id}>
                    <td className="sg-num">{chunk.page_number}</td>
                    <td>
                      <div>{sectionPathText(chunk)}</div>
                      <div className="sg-mono">
                        H1 {chunk.heading_1 ?? "—"} / H2 {chunk.heading_2 ?? "—"}{" "}
                        / H3 {chunk.heading_3 ?? "—"}
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
            <p className="sg-mono">
              本页 {chunksResult.value.items.length} 条，后端 total{" "}
              {chunksResult.value.total}
              {chunksResult.value.has_next
                ? "（仍有后续页，本页只取第一页）"
                : ""}
            </p>
          </>
        )}
      </section>

      {/* 参考文献与引用对应 */}
      <section className="sg-section">
        <div className="sg-section__head">
          <h2 className="sg-section__title">
            参考文献与引用对应 · ReferenceEntry / CitationLink
          </h2>
          <span className="sg-section__hint">
            GET /references 与 /citation-links · 分页
          </span>
        </div>

        {refsResult.kind === "error" ? (
          <ErrorState title="参考文献取数失败" error={refsResult.error} />
        ) : refs.length === 0 ? (
          <p>后端返回 0 条参考文献条目。</p>
        ) : (
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
              {refs.map((ref) => (
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
        )}

        <h3 className="sg-subhead">正文 ↔ 文末 对应关系</h3>
        {linksResult.kind === "error" ? (
          <ErrorState title="引用对应取数失败" error={linksResult.error} />
        ) : links.length === 0 ? (
          <p>后端返回 0 条引用对应关系。</p>
        ) : (
          <table className="sg-table">
            <thead>
              <tr>
                <th className="sg-num">引用序号</th>
                <th className="sg-num">所在页</th>
                <th className="sg-num">所在分块</th>
                <th className="sg-num">目标条目</th>
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
                      {target ? (
                        <div className="sg-tag sg-tag--muted">
                          → {target.title ?? "—"}
                        </div>
                      ) : null}
                    </td>
                    <td>
                      <p className="sg-prose">{chunk?.text ?? "—"}</p>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </section>

      {/* 去重与差异：无记录时后端 404，页面显示暂无，不编造假记录 */}
      <section className="sg-section">
        <div className="sg-section__head">
          <h2 className="sg-section__title">去重与版本差异</h2>
          <span className="sg-section__hint">
            GET /dedup-decision 与 /diff-summary · 路径参数为新版 id
          </span>
        </div>

        <h3 className="sg-subhead">版本裁决 · DedupDecision</h3>
        {dedupResult.kind === "error" ? (
          <ErrorState title="去重裁决取数失败" error={dedupResult.error} />
        ) : dedupResult.value === null ? (
          <p>暂无去重记录（后端返回 404，该论文不是新版）。</p>
        ) : (
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
              <tr>
                <td className="sg-mono">{dedupResult.value.old_paper_id}</td>
                <td className="sg-mono">{dedupResult.value.new_paper_id}</td>
                <td className="sg-num">{dedupResult.value.similarity}</td>
                <td>
                  <span className="sg-tag sg-tag--info">
                    {dedupResult.value.recommendation}
                  </span>
                </td>
                <td className="sg-mono">
                  {String(dedupResult.value.human_override)}
                </td>
                <td>
                  {dedupResult.value.evidence.map((item, index) => (
                    <div key={index}>
                      <span className="sg-anchor">
                        p.{item.anchor.page_number} · {item.anchor.chunk_id}
                      </span>
                      <div>{item.reason}</div>
                    </div>
                  ))}
                </td>
              </tr>
            </tbody>
          </table>
        )}

        <h3 className="sg-subhead">版本差异摘要 · DiffSummary</h3>
        {diffResult.kind === "error" ? (
          <ErrorState title="版本差异取数失败" error={diffResult.error} />
        ) : diffResult.value === null ? (
          <p>暂无差异记录（后端返回 404，该论文不是新版）。</p>
        ) : (
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
              <tr>
                <td>
                  {diffResult.value.changed_sections.length > 0
                    ? diffResult.value.changed_sections.join("；")
                    : "未检出章节级差异"}
                </td>
                <td>{diffResult.value.summary_text}</td>
                <td>
                  {diffResult.value.key_sentences.map((sentence, index) => (
                    <div key={index}>
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
                  {diffResult.value.key_sentences.map((sentence, index) => (
                    <div key={index}>
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
            </tbody>
          </table>
        )}
      </section>

      <UnavailablePanel area="paper" />
    </main>
  );
}

export const dynamic = "force-dynamic";

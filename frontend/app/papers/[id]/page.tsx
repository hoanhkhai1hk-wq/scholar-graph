import Link from "next/link";
import {
  fetchChunks,
  fetchCitationLinks,
  fetchDedupDecision,
  fetchDiffSummary,
  fetchPaper,
  fetchParseStatus,
  fetchReferences,
  MAX_PAGE_SIZE,
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
import Diagnostics from "@/components/Diagnostics";
import ParseStatusLive from "@/components/ParseStatusLive";
import PaperExtensions from "@/components/PaperExtensions";

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

const SUB_PAGE_SIZE = 20;

function parsePositiveInt(raw: string | undefined, fallback: number): number {
  const value = Number(raw);
  if (!Number.isInteger(value) || value < 1) return fallback;
  return value;
}

/**
 * 子资源分页控件。翻页按后端返回的 total_pages 与 has_next 控制，
 * 其余子资源的当前页码通过查询参数保留，避免翻一个区丢掉另外两个区的位置。
 */
function SubPagination({
  param,
  page,
  paged,
  current,
}: {
  param: string;
  page: number;
  paged: Paged<unknown>;
  current: Record<string, number>;
}) {
  const href = (target: number) => {
    const params = new URLSearchParams();
    for (const [key, value] of Object.entries(current)) {
      params.set(key, String(key === param ? target : value));
    }
    params.set(param, String(target));
    return `?${params.toString()}`;
  };

  return (
    <div className="sg-pagination">
      {page > 1 ? (
        <Link className="sg-pagination__link" href={href(page - 1)}>
          上一页
        </Link>
      ) : (
        <span className="sg-pagination__link sg-pagination__link--disabled">
          上一页
        </span>
      )}
      <span>
        第 {paged.page} / {paged.total_pages} 页 · total {paged.total} ·
        has_next {String(paged.has_next)}
      </span>
      {paged.has_next ? (
        <Link className="sg-pagination__link" href={href(page + 1)}>
          下一页
        </Link>
      ) : (
        <span className="sg-pagination__link sg-pagination__link--disabled">
          下一页
        </span>
      )}
    </div>
  );
}

function sectionPathText(chunk: Chunk): string {
  return chunk.section_path.length > 0
    ? chunk.section_path.join(" / ")
    : "（无章节标题）";
}

export default async function PaperDetailPage({
  params,
  searchParams,
}: {
  params: Promise<{ id: string }>;
  searchParams: Promise<{
    chunks_page?: string;
    refs_page?: string;
    links_page?: string;
  }>;
}) {
  const { id } = await params;
  const query = await searchParams;

  const chunksPage = parsePositiveInt(query.chunks_page, 1);
  const refsPage = parsePositiveInt(query.refs_page, 1);
  const linksPage = parsePositiveInt(query.links_page, 1);
  const current = {
    chunks_page: chunksPage,
    refs_page: refsPage,
    links_page: linksPage,
  };

  const paperResult = await settle(fetchPaper(id));

  if (paperResult.kind === "error") {
    return (
      <main className="sg-shell sg-paper-detail">
        <p className="sg-back">
          <Link href="/">← 返回论文库</Link>
        </p>
        <div className="sg-page-head">
          <Diagnostics summary="技术信息（接口路径与契约字段）">GET /api/v1/papers/{id}</Diagnostics>
          <h1 className="sg-title">论文详情</h1>
        </div>
        <section className="sg-section">
          <div className="sg-section__head">
            <h2 className="sg-section__title">取数失败</h2>
            <Diagnostics summary="接口与分页信息">未取得该论文</Diagnostics>
          </div>
          <ErrorState title="论文详情取数失败" error={paperResult.error} />
        </section>
      </main>
    );
  }

  const paper: PaperMeta = paperResult.value;

  const [chunksResult, refsResult, linksResult, statusResult, dedupResult, diffResult] =
    await Promise.all([
      settle<Paged<Chunk>>(
        fetchChunks(id, { page: chunksPage, pageSize: SUB_PAGE_SIZE }),
      ),
      settle<Paged<ReferenceEntry>>(
        fetchReferences(id, { page: refsPage, pageSize: SUB_PAGE_SIZE }),
      ),
      settle<Paged<CitationLink>>(
        fetchCitationLinks(id, { page: linksPage, pageSize: SUB_PAGE_SIZE }),
      ),
      settle<ParseStatus>(fetchParseStatus(id)),
      settle<DedupDecision | null>(fetchDedupDecision(id)),
      settle<DiffSummary | null>(fetchDiffSummary(id)),
    ]);

  // 引用对应表需要显示正文片段，额外取当页引用所在的分块
  let chunkMap = new Map<string, Chunk>();
  if (linksResult.kind === "ok" && chunksResult.kind === "ok") {
    for (const chunk of chunksResult.value.items) {
      chunkMap.set(chunk.chunk_id, chunk);
    }
  }

  return (
    <main className="sg-shell sg-paper-detail">
      <p className="sg-back">
        <Link href="/">← 返回论文库</Link>
      </p>

      <div className="sg-page-head">
        <Diagnostics summary="技术信息（接口路径与契约字段）">GET /api/v1/papers/{id}</Diagnostics>
        <h1 className="sg-title">{paper.title ?? "（标题未提取）"}</h1>
        <p className="sg-lede">{paper.abstract ?? "（摘要未提供）"}</p>
        <p className="sg-back">
          <Link href={`/read/${id}`}>打开阅读器（章节导航与引用跳转）→</Link>
        </p>
      </div>

      {/* 解析状态：非终态时前端轮询，到达终态即停 */}
      <section className="sg-section">
        <div className="sg-section__head">
          <h2 className="sg-section__title">解析状态</h2>
          <Diagnostics summary="接口与分页信息">
            GET /papers/{id}/parse-status · 非终态轮询，终态停止
          </Diagnostics>
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
          <h2 className="sg-section__title">分块列表</h2>
          <Diagnostics summary="接口与分页信息">
            GET /papers/{id}/chunks · 每页 {SUB_PAGE_SIZE} 条（上限{" "}
            {MAX_PAGE_SIZE}）
          </Diagnostics>
        </div>
        {chunksResult.kind === "error" ? (
          <ErrorState title="分块列表取数失败" error={chunksResult.error} />
        ) : chunksResult.value.items.length === 0 ? (
          <p>本页没有正文分块，共 {chunksResult.value.total} 条。</p>
        ) : (
          <div className="sg-table-scroll" role="region" aria-label="论文解析数据表，可横向滚动" tabIndex={0}><table className="sg-table">
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
                      H1 {chunk.heading_1 ?? "—"} / H2 {chunk.heading_2 ?? "—"} /
                      H3 {chunk.heading_3 ?? "—"}
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
          </table></div>
        )}
        {chunksResult.kind === "ok" ? (
          <SubPagination
            param="chunks_page"
            page={chunksPage}
            paged={chunksResult.value}
            current={current}
          />
        ) : null}
      </section>

      {/* 参考文献 */}
      <section className="sg-section">
        <div className="sg-section__head">
          <h2 className="sg-section__title">参考文献</h2>
          <Diagnostics summary="接口与分页信息">
            GET /papers/{id}/references · 每页 {SUB_PAGE_SIZE} 条
          </Diagnostics>
        </div>
        {refsResult.kind === "error" ? (
          <ErrorState title="参考文献取数失败" error={refsResult.error} />
        ) : refsResult.value.items.length === 0 ? (
          <p>本页没有参考文献条目，共 {refsResult.value.total} 条。</p>
        ) : (
          <div className="sg-table-scroll" role="region" aria-label="论文解析数据表，可横向滚动" tabIndex={0}><table className="sg-table">
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
              {refsResult.value.items.map((ref) => (
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
          </table></div>
        )}
        {refsResult.kind === "ok" ? (
          <SubPagination
            param="refs_page"
            page={refsPage}
            paged={refsResult.value}
            current={current}
          />
        ) : null}
      </section>

      {/* 引用对应 */}
      <section className="sg-section">
        <div className="sg-section__head">
          <h2 className="sg-section__title">
            正文 ↔ 文末 对应关系
          </h2>
          <Diagnostics summary="接口与分页信息">
            GET /papers/{id}/citation-links · 每页 {SUB_PAGE_SIZE} 条
          </Diagnostics>
        </div>
        {linksResult.kind === "error" ? (
          <ErrorState title="引用对应取数失败" error={linksResult.error} />
        ) : linksResult.value.items.length === 0 ? (
          <p>本页没有引用对应关系，共 {linksResult.value.total} 条。</p>
        ) : (
          <div className="sg-table-scroll" role="region" aria-label="论文解析数据表，可横向滚动" tabIndex={0}><table className="sg-table">
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
              {linksResult.value.items.map((link) => {
                const chunk = chunkMap.get(link.chunk_id);
                return (
                  <tr
                    key={`${link.citation_number}-${link.page_number}-${link.chunk_id}`}
                  >
                    <td className="sg-num">[{link.citation_number}]</td>
                    <td className="sg-num">{link.page_number}</td>
                    <td className="sg-mono">{link.chunk_id}</td>
                    <td className="sg-mono">{link.ref_id}</td>
                    <td>
                      {chunk ? (
                        <p className="sg-prose">{chunk.text}</p>
                      ) : (
                        <span className="sg-mono">
                          该分块不在当前分块页，请翻到对应分块页查看
                        </span>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table></div>
        )}
        {linksResult.kind === "ok" ? (
          <>
            <SubPagination
              param="links_page"
              page={linksPage}
              paged={linksResult.value}
              current={current}
            />
            <p className="sg-mono">
              说明：正文片段取自当前分块页，若引用所在分块不在本页，
              请翻到对应分块页；完整阅读请用阅读器。
            </p>
          </>
        ) : null}
      </section>

      {/* 去重与差异：无记录时后端 404，页面显示暂无，不编造假记录 */}
      <section className="sg-section">
        <div className="sg-section__head">
          <h2 className="sg-section__title">去重与版本差异</h2>
          <Diagnostics summary="接口与分页信息">
            GET /dedup-decision 与 /diff-summary · 路径参数为新版 id
          </Diagnostics>
        </div>

        <h3 className="sg-subhead">版本裁决 · DedupDecision</h3>
        {dedupResult.kind === "error" ? (
          <ErrorState title="去重裁决取数失败" error={dedupResult.error} />
        ) : dedupResult.value === null ? (
          <p>暂无去重记录（后端返回 404，该论文不是新版）。</p>
        ) : (
          <div className="sg-table-scroll" role="region" aria-label="论文解析数据表，可横向滚动" tabIndex={0}><table className="sg-table">
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
          </table></div>
        )}

        <h3 className="sg-subhead">版本差异摘要 · DiffSummary</h3>
        {diffResult.kind === "error" ? (
          <ErrorState title="版本差异取数失败" error={diffResult.error} />
        ) : diffResult.value === null ? (
          <p>暂无差异记录（后端返回 404，该论文不是新版）。</p>
        ) : (
          <div className="sg-table-scroll" role="region" aria-label="论文解析数据表，可横向滚动" tabIndex={0}><table className="sg-table">
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
          </table></div>
        )}
      </section>

      <PaperExtensions paperId={id} />
    </main>
  );
}

export const dynamic = "force-dynamic";

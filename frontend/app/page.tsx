import Link from "next/link";
import { fetchPapers, MAX_PAGE_SIZE } from "@/lib/api";
import type { Paged, PaperMeta } from "@/lib/types";
import ErrorState from "@/components/ErrorState";
import CapabilityIndex from "@/components/CapabilityIndex";
import EmptyState from "@/components/EmptyState";
import Diagnostics from "@/components/Diagnostics";

type Loaded =
  | { kind: "ok"; data: Paged<PaperMeta>; page: number }
  | { kind: "error"; error: unknown; page: number; pageSize: number };

function parsePositiveInt(raw: string | undefined, fallback: number): number {
  const value = Number(raw);
  if (!Number.isInteger(value) || value < 1) return fallback;
  return value;
}

export default async function HomePage({
  searchParams,
}: {
  searchParams: Promise<{ page?: string; page_size?: string }>;
}) {
  const params = await searchParams;
  const requestedPage = parsePositiveInt(params.page, 1);
  const requestedSize = parsePositiveInt(params.page_size, 20);
  const pageSize = Math.min(requestedSize, MAX_PAGE_SIZE);

  let loaded: Loaded;
  try {
    const data = await fetchPapers({ page: requestedPage, pageSize });
    loaded = { kind: "ok", data, page: requestedPage };
  } catch (error) {
    loaded = { kind: "error", error, page: requestedPage, pageSize };
  }

  if (loaded.kind === "ok") {
    const { data } = loaded;
    const buildHref = (page: number) =>
      `/?page=${page}&page_size=${data.page_size}`;

    return (
      <main className="sg-shell">
        <div className="sg-page-head">
          <h1 className="sg-title">我的论文</h1>
          <p className="sg-lede">
            上传论文后即可阅读、提问、对照引用。每一条回答都能点回原文的那一页。
          </p>
          <div className="sg-form">
            <Link className="sg-btn" href="/upload">
              上传论文
            </Link>
            <Link className="sg-btn sg-btn--ghost" href="/qa">
              去提问
            </Link>
          </div>
          <Diagnostics>
            GET /api/v1/papers · 分页壳 items / page / page_size / total /
            total_pages / has_next；翻页按后端返回的 total_pages 与 has_next 控制，
            不自行推算总数。
          </Diagnostics>
        </div>

        <section className="sg-section">
          <div className="sg-section__head">
            <h2 className="sg-section__title">工作台</h2>
            <span className="sg-section__hint">
              共 {data.total} 篇 · 第 {data.page} / {data.total_pages} 页
            </span>
          </div>

          <div className="sg-bento">
            <div className="sg-bento__cell sg-bento__cell--third">
              <p className="sg-bento__label">库内论文</p>
              <p className="sg-bento__figure">{data.total}</p>
              <p className="sg-mono">解析状态在下方列表逐篇可见</p>
            </div>
            <div className="sg-bento__cell sg-bento__cell--third">
              <p className="sg-bento__label">本页条目</p>
              <p className="sg-bento__figure">{data.items.length}</p>
              <p className="sg-mono">每页 {data.page_size} 条</p>
            </div>
            <div className="sg-bento__cell sg-bento__cell--third">
              <p className="sg-bento__label">有文本层</p>
              <p className="sg-bento__figure">
                {data.items.filter((paper) => paper.has_text_layer).length}
              </p>
              <p className="sg-mono">
                无文本层 {data.items.filter((p) => !p.has_text_layer).length} 篇走 OCR
              </p>
            </div>

            <div className="sg-bento__cell sg-bento__cell--full">
              <p className="sg-bento__label">从这里开始</p>
              <div className="sg-entries">
                <Link className="sg-entry-card" href="/qa">
                  <p className="sg-entry-card__title">单篇 / 跨篇问答</p>
                  <p className="sg-entry-card__meta">答案带四字段原文锚点</p>
                </Link>
                <Link className="sg-entry-card" href="/graph">
                  <p className="sg-entry-card__title">引用图谱</p>
                  <p className="sg-entry-card__meta">只画已核验的引用边</p>
                </Link>
                <Link className="sg-entry-card" href="/retrieval">
                  <p className="sg-entry-card__title">公开检索与追踪</p>
                  <p className="sg-entry-card__meta">arXiv 抓取与每日追踪</p>
                </Link>
                <Link className="sg-entry-card" href="/writing">
                  <p className="sg-entry-card__title">写作辅助</p>
                  <p className="sg-entry-card__meta">框架、摘录草稿、CSV 图表</p>
                </Link>
                <Link className="sg-entry-card" href="/upload">
                  <p className="sg-entry-card__title">上传论文</p>
                  <p className="sg-entry-card__meta">支持批量与扫描件 OCR</p>
                </Link>
              </div>
            </div>
          </div>
        </section>

        <section className="sg-section">
          <div className="sg-section__head">
            <h2 className="sg-section__title">论文列表</h2>
            <span className="sg-section__hint">
              共 {data.total} 条 · 每页 {data.page_size} 条
            </span>
          </div>

          {data.items.length === 0 ? (
            <EmptyState
              title="库里还没有论文"
              hint="上传第一篇 PDF 后，这里会显示标题、作者、年份与处理状态。也可以先上传命题提供的官方测试论文试一遍流程。"
              aside={`total=${data.total} · total_pages=${data.total_pages} · has_next=${String(data.has_next)}`}
              action={
                <>
                  <Link className="sg-btn" href="/upload">
                    上传第一篇论文
                  </Link>
                  <Link className="sg-btn sg-btn--ghost" href="/upload">
                    批量上传
                  </Link>
                </>
              }
            />
          ) : (
            <table className="sg-table">
              <thead>
                <tr>
                  <th>标题</th>
                  <th>作者</th>
                  <th className="sg-num">年份</th>
                  <th className="sg-num">版本</th>
                  <th className="sg-num">页数</th>
                  <th>文本层</th>
                  <th>来源</th>
                  <th>标识</th>
                </tr>
              </thead>
              <tbody>
                {data.items.map((paper) => (
                  <tr key={paper.id}>
                    <td>
                      <Link href={`/papers/${paper.id}`}>
                        {paper.title ?? "（标题未提取）"}
                      </Link>
                      <div className="sg-mono">{paper.id}</div>
                      <Link className="sg-rowlink" href={`/read/${paper.id}`}>
                        阅读器
                      </Link>
                    </td>
                    <td>
                      {paper.authors.join("; ")}
                      <div className="sg-mono">
                        {paper.institutions.join("; ")}
                      </div>
                    </td>
                    <td className="sg-num">{paper.year ?? "—"}</td>
                    <td className="sg-num">{paper.version ?? "—"}</td>
                    <td className="sg-num">{paper.page_count ?? "—"}</td>
                    <td>
                      {paper.has_text_layer === null ? (
                        <span className="sg-tag sg-tag--muted">未检查</span>
                      ) : paper.has_text_layer ? (
                        <span className="sg-tag sg-tag--success">有</span>
                      ) : (
                        <span className="sg-tag sg-tag--warning">无</span>
                      )}
                    </td>
                    <td>{paper.source ?? "—"}</td>
                    <td>
                      <div className="sg-mono">
                        {paper.arxiv_id ? `arXiv ${paper.arxiv_id}` : "arXiv —"}
                      </div>
                      <div className="sg-mono">
                        {paper.doi ? `DOI ${paper.doi}` : "DOI —"}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}

          <div className="sg-pagination">
            {loaded.page > 1 ? (
              <Link
                className="sg-pagination__link"
                href={buildHref(loaded.page - 1)}
              >
                上一页
              </Link>
            ) : (
              <span className="sg-pagination__link sg-pagination__link--disabled">
                上一页
              </span>
            )}
            <span>
              第 {data.page} 页 / 共 {data.total_pages} 页 · total{" "}
              {data.total} · has_next {String(data.has_next)}
            </span>
            {data.has_next ? (
              <Link
                className="sg-pagination__link"
                href={buildHref(loaded.page + 1)}
              >
                下一页
              </Link>
            ) : (
              <span className="sg-pagination__link sg-pagination__link--disabled">
                下一页
              </span>
            )}
          </div>
        </section>

        <div className="sg-diag">
          <details className="sg-diag">
            <summary className="sg-diag__summary">
              能力端点总表（按模块列出已落地的接口）
            </summary>
            <div className="sg-diag__body">
              <CapabilityIndex />
            </div>
          </details>
        </div>
      </main>
    );
  }

  return (
    <main className="sg-shell">
      <div className="sg-page-head">
        <Diagnostics summary="技术信息（接口路径与分页字段）">GET /api/v1/papers</Diagnostics>
        <h1 className="sg-title">论文库</h1>
        <p className="sg-lede">
          请求第 {loaded.page} 页、每页 {loaded.pageSize} 条时后端未返回数据。
        </p>
      </div>
      <section className="sg-section">
        <div className="sg-section__head">
          <h2 className="sg-section__title">论文列表</h2>
          <span className="sg-section__hint">取数失败</span>
        </div>
        <ErrorState title="论文列表取数失败" error={loaded.error} />
      </section>
    </main>
  );
}

export const dynamic = "force-dynamic";

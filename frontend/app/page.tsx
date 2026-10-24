import Link from "next/link";
import { fetchPapers, MAX_PAGE_SIZE } from "@/lib/api";
import type { Paged, PaperMeta } from "@/lib/types";
import ErrorState from "@/components/ErrorState";
import CapabilityIndex from "@/components/CapabilityIndex";

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
          <p className="sg-eyebrow">GET /api/v1/papers</p>
          <h1 className="sg-title">论文库</h1>
          <p className="sg-lede">
            数据来自模块一已落地的列表端点，使用统一分页壳
            items / page / page_size / total / total_pages / has_next。
            翻页完全按后端返回的 total_pages 与 has_next 控制，不自行推算总数。
          </p>
          <p className="sg-back">
            <Link href="/upload">上传 PDF →</Link>
          </p>
        </div>

        <section className="sg-section">
          <div className="sg-section__head">
            <h2 className="sg-section__title">PaperMeta 分页列表</h2>
            <span className="sg-section__hint">
              第 {data.page} / {data.total_pages} 页 · 共 {data.total} 条 · 每页{" "}
              {data.page_size} 条
            </span>
          </div>

          {data.items.length === 0 ? (
            <p>
              本页无记录（total={data.total}）。空集合时 total_pages 为 0、
              has_next 为 false，页面不编造条目。
            </p>
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

        <CapabilityIndex />
      </main>
    );
  }

  return (
    <main className="sg-shell">
      <div className="sg-page-head">
        <p className="sg-eyebrow">GET /api/v1/papers</p>
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

import { fetchPapers } from "@/lib/api";
import GraphWorkspace from "@/components/GraphWorkspace";
import ErrorState from "@/components/ErrorState";

export default async function GraphPage() {
  let papers: Awaited<ReturnType<typeof fetchPapers>>["items"] = [];
  let error: unknown = null;
  try {
    const paged = await fetchPapers({ page: 1, pageSize: 100 });
    papers = paged.items;
  } catch (cause) {
    error = cause;
  }

  return (
    <main className="sg-shell">
      <div className="sg-page-head">
        <p className="sg-eyebrow">GET /api/v1/graph</p>
        <h1 className="sg-title">局域引用图谱</h1>
        <p className="sg-lede">
          只读本地已落盘记录：节点按 paper_id 排序，分层按 PageRank 降序；
          无锚点的边原样标 unverified，不画成已核验边；未来方向的已排除与保留分开列。
        </p>
        <p className="sg-back">
          <a href="/">← 返回论文库</a>
        </p>
      </div>

      {error ? (
        <section className="sg-section">
          <div className="sg-section__head">
            <h2 className="sg-section__title">论文列表取数失败</h2>
            <span className="sg-section__hint">无法提供可选论文</span>
          </div>
          <ErrorState title="论文列表取数失败" error={error} />
        </section>
      ) : (
        <GraphWorkspace papers={papers} />
      )}
    </main>
  );
}

export const dynamic = "force-dynamic";

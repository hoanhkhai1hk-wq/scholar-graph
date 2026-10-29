import { fetchPapers } from "@/lib/api";
import GraphWorkspace from "@/components/GraphWorkspace";
import Diagnostics from "@/components/Diagnostics";
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
        <Diagnostics summary="技术信息（接口路径与算法口径）">GET /api/v1/graph</Diagnostics>
        <h1 className="sg-title">局域引用图谱</h1>
        <p className="sg-lede">
          从一组真实文献中找出引用关系、核心节点与衍生研究，逐条查看原文依据，并继续生成综述。
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

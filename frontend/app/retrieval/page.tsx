import { fetchPapers } from "@/lib/api";
import RetrievalWorkspace from "@/components/RetrievalWorkspace";
import Diagnostics from "@/components/Diagnostics";
import ErrorState from "@/components/ErrorState";

export default async function RetrievalPage() {
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
        <Diagnostics summary="技术信息（接口路径与评分口径）">
          POST /retrieval/search · /retrieval/fetch · GET /recommendations
        </Diagnostics>
        <h1 className="sg-title">发现与追踪</h1>
        <p className="sg-lede">
          查找公开论文、批量获取参考文献，并按你的研究主题发现和追踪新工作。
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
        <RetrievalWorkspace papers={papers} />
      )}
    </main>
  );
}

export const dynamic = "force-dynamic";

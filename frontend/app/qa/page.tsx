import { fetchPapers } from "@/lib/api";
import QaWorkspace from "@/components/ResearchChat";
import Diagnostics from "@/components/Diagnostics";
import ErrorState from "@/components/ErrorState";

export default async function QaPage() {
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
        <Diagnostics summary="技术信息（接口路径与编排口径）">POST /api/v2/sessions/{`{id}`}/messages/stream</Diagnostics>
        <h1 className="sg-title">问答与跨篇对比</h1>
        <p className="sg-lede">
          选择论文后直接提问，比较多篇研究的方法和结果。点击回答中的证据，可以查看对应原文。
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
        <QaWorkspace papers={papers} />
      )}
    </main>
  );
}

export const dynamic = "force-dynamic";

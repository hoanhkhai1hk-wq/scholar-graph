import { fetchPapers } from "@/lib/api";
import QaWorkspace from "@/components/QaWorkspace";
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
        <p className="sg-eyebrow">POST /api/v1/papers/{`{id}`}/qa · /compare</p>
        <h1 className="sg-title">问答与跨篇对比</h1>
        <p className="sg-lede">
          选中一篇走单篇问答，选中多篇走跨篇对比。答案逐条对应 Chunk 锚点，
          refused=true 时原样展示拒答原因与原文纠错，不把拒答渲染成答案。
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

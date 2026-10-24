import { fetchPapers } from "@/lib/api";
import WritingWorkspace from "@/components/WritingWorkspace";
import ErrorState from "@/components/ErrorState";

export default async function WritingPage() {
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
        <p className="sg-eyebrow">
          POST /frameworks · /reviews · /charts/csv
        </p>
        <h1 className="sg-title">综述框架、摘录草稿与图表</h1>
        <p className="sg-lede">
          框架给出章节结构与待写要点（原文摘录）；摘录草稿逐条标注 verified /
          unverifiable；CSV 图表展示图注数字与 CSV 单元格的回溯关系。
          全部为摘录与回溯结果，不是模型自由成文。
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
        <WritingWorkspace papers={papers} />
      )}
    </main>
  );
}

export const dynamic = "force-dynamic";

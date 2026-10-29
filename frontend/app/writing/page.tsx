import { fetchPapers } from "@/lib/api";
import WritingWorkspace from "@/components/WritingWorkspace";
import Diagnostics from "@/components/Diagnostics";
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
        <Diagnostics summary="技术信息（接口路径与图注口径）">
          POST /frameworks · /reviews · /charts/csv
        </Diagnostics>
        <h1 className="sg-title">写作工作台</h1>
        <p className="sg-lede">
          从研究想法生成论文框架、文献综述和方法拓扑，结合原文核对依据；
          上传 CSV 生成表格、折线图、柱状图和三维雷达图。
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

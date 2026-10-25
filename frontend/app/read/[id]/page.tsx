import Link from "next/link";
import {
  fetchAllPages,
  fetchChunks,
  fetchCitationLinks,
  fetchPaper,
  fetchReferences,
} from "@/lib/api";
import ReaderWorkspace from "@/components/ReaderWorkspace";
import ErrorState from "@/components/ErrorState";

export default async function ReaderPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;

  const paperResult = await fetchPaper(id).then(
    (value) => ({ kind: "ok", value }) as const,
    (error) => ({ kind: "error", error }) as const,
  );

  if (paperResult.kind === "error") {
    return (
      <main className="sg-shell">
        <p className="sg-back">
          <Link href="/">← 返回论文库</Link>
        </p>
        <div className="sg-page-head">
          <p className="sg-eyebrow">GET /api/v1/papers/{id}</p>
          <h1 className="sg-title">阅读器</h1>
        </div>
        <section className="sg-section">
          <div className="sg-section__head">
            <h2 className="sg-section__title">取数失败</h2>
            <span className="sg-section__hint">未取得该论文</span>
          </div>
          <ErrorState title="论文详情取数失败" error={paperResult.error} />
        </section>
      </main>
    );
  }

  const paper = paperResult.value;

  const [chunksResult, refsResult, linksResult] = await Promise.all([
    fetchAllPages((page) => fetchChunks(id, { page, pageSize: 100 })).then(
      (value) => ({ kind: "ok", value }) as const,
      (error) => ({ kind: "error", error }) as const,
    ),
    fetchAllPages((page) => fetchReferences(id, { page, pageSize: 100 })).then(
      (value) => ({ kind: "ok", value }) as const,
      (error) => ({ kind: "error", error }) as const,
    ),
    fetchAllPages((page) =>
      fetchCitationLinks(id, { page, pageSize: 100 }),
    ).then(
      (value) => ({ kind: "ok", value }) as const,
      (error) => ({ kind: "error", error }) as const,
    ),
  ]);

  if (
    chunksResult.kind === "error" ||
    refsResult.kind === "error" ||
    linksResult.kind === "error"
  ) {
    return (
      <main className="sg-shell">
        <p className="sg-back">
          <Link href="/">← 返回论文库</Link>
        </p>
        <div className="sg-page-head">
          <p className="sg-eyebrow">阅读器</p>
          <h1 className="sg-title">{paper.title ?? "（标题未提取）"}</h1>
        </div>
        {chunksResult.kind === "error" ? (
          <section className="sg-section">
            <div className="sg-section__head">
              <h2 className="sg-section__title">分块取数失败</h2>
              <span className="sg-section__hint">GET /chunks</span>
            </div>
            <ErrorState title="分块取数失败" error={chunksResult.error} />
          </section>
        ) : null}
        {refsResult.kind === "error" ? (
          <section className="sg-section">
            <div className="sg-section__head">
              <h2 className="sg-section__title">参考文献取数失败</h2>
              <span className="sg-section__hint">GET /references</span>
            </div>
            <ErrorState title="参考文献取数失败" error={refsResult.error} />
          </section>
        ) : null}
        {linksResult.kind === "error" ? (
          <section className="sg-section">
            <div className="sg-section__head">
              <h2 className="sg-section__title">引用对应取数失败</h2>
              <span className="sg-section__hint">GET /citation-links</span>
            </div>
            <ErrorState title="引用对应取数失败" error={linksResult.error} />
          </section>
        ) : null}
      </main>
    );
  }

  const truncated =
    chunksResult.value.truncated ||
    refsResult.value.truncated ||
    linksResult.value.truncated;

  return (
    <main className="sg-shell sg-shell--wide">
      <div className="sg-page-head">
        <p className="sg-eyebrow">
          Chunk / ReferenceEntry / CitationLink 已落盘材料
        </p>
        <h1 className="sg-title">{paper.title ?? "（标题未提取）"}</h1>
        <p className="sg-lede">
          章节导航按 section_path 与物理页码组织；点正文引用跳到文末条目，
          点文末条目跳回引用它的 Chunk。
          <Link href={`/papers/${id}`}>查看该论文详情</Link>。
        </p>
        <p className="sg-back">
          <Link href="/">← 返回论文库</Link>
        </p>
      </div>

      {truncated ? (
        <div className="sg-note">
          <span className="sg-tag sg-tag--warning">材料可能不完整</span>
          <p className="sg-note__text">
            子资源页数超过单次抓取上限，本页只加载了前若干页；
            完整材料需要后端分页端点补齐或后续提供聚合端点。
          </p>
        </div>
      ) : null}

      <ReaderWorkspace
        paperId={id}
        chunks={chunksResult.value.items}
        references={refsResult.value.items}
        links={linksResult.value.items}
      />
    </main>
  );
}

export const dynamic = "force-dynamic";

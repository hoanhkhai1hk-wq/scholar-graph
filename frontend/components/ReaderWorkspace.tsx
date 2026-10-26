"use client";

import { useState } from "react";
import type { Chunk, CitationLink, ReferenceEntry } from "@/lib/types";
import ReaderPane from "./ReaderPane";
import TranslatePanel from "./TranslatePanel";
import LayoutViewer from "./LayoutViewer";

/**
 * 阅读器工作区：原文阅读 / 中英双语对照 / 版式原文 三个视图切换。
 * 三个视图互不改动：文本 pane 与双语同步滚动保持原样，版式原文只负责 PDF 原件渲染。
 */
export default function ReaderWorkspace({
  chunks,
  references,
  links,
  paperId,
}: {
  chunks: Chunk[];
  references: ReferenceEntry[];
  links: CitationLink[];
  paperId: string;
}) {
  const [view, setView] = useState<"read" | "bilingual" | "layout">("read");

  return (
    <div>
      <div className="sg-form sg-form--inline">
        <label className="sg-checkbox">
          <input
            type="radio"
            name="reader-view"
            checked={view === "read"}
            onChange={() => setView("read")}
          />
          原文阅读
        </label>
        <label className="sg-checkbox">
          <input
            type="radio"
            name="reader-view"
            checked={view === "bilingual"}
            onChange={() => setView("bilingual")}
          />
          中英双语对照
        </label>
        <label className="sg-checkbox">
          <input
            type="radio"
            name="reader-view"
            checked={view === "layout"}
            onChange={() => setView("layout")}
          />
          版式原文（pdf.js）
        </label>
      </div>

      {view === "layout" ? (
        <section className="sg-section">
          <div className="sg-section__head">
            <h2 className="sg-section__title">版式原文</h2>
            <span className="sg-section__hint">
              GET /api/v1/papers/{"{id}"}/file · pdf.js 逐页渲染原件
            </span>
          </div>
          <LayoutViewer
            paperId={paperId}
            chunks={chunks}
            references={references}
            links={links}
          />
        </section>
      ) : view === "read" ? (
        <ReaderPane
          chunks={chunks}
          references={references}
          links={links}
        />
      ) : (
        <section className="sg-section">
          <div className="sg-section__head">
            <h2 className="sg-section__title">中英双语对照</h2>
            <span className="sg-section__hint">
              POST /api/v1/papers/{"{id}"}/translate · 按 source_chunk_id 对齐
            </span>
          </div>
          <TranslatePanel paperId={paperId} chunks={chunks} />
        </section>
      )}
    </div>
  );
}

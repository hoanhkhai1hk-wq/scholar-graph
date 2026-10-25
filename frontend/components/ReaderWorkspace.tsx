"use client";

import { useState } from "react";
import type { Chunk, CitationLink, ReferenceEntry } from "@/lib/types";
import ReaderPane from "./ReaderPane";
import TranslatePanel from "./TranslatePanel";

/**
 * 阅读器工作区：原文阅读 / 中英双语对照 两个视图切换。
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
  const [view, setView] = useState<"read" | "bilingual">("read");

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
      </div>

      {view === "read" ? (
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

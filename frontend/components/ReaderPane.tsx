"use client";

import { useMemo, useRef, useState } from "react";
import type { Chunk, CitationLink, ReferenceEntry } from "@/lib/types";

interface ChapterGroup {
  key: string;
  title: string;
  pages: number[];
  chunkIds: string[];
}

function buildChapters(chunks: Chunk[]): ChapterGroup[] {
  const groups = new Map<string, ChapterGroup>();
  for (const chunk of chunks) {
    const key =
      chunk.section_path.length > 0
        ? chunk.section_path.join(" / ")
        : "(未分章节)";
    const existing = groups.get(key);
    if (existing) {
      if (!existing.pages.includes(chunk.page_number)) {
        existing.pages.push(chunk.page_number);
      }
      existing.chunkIds.push(chunk.chunk_id);
    } else {
      groups.set(key, {
        key,
        title: key,
        pages: [chunk.page_number],
        chunkIds: [chunk.chunk_id],
      });
    }
  }
  return [...groups.values()].sort((a, b) => {
    const pa = Math.min(...a.pages);
    const pb = Math.min(...b.pages);
    return pa === pb ? a.title.localeCompare(b.title) : pa - pb;
  });
}

/** 把正文中的 [1]、[1, 3]、[2–4] 之类引用标记拆成按钮 */
function renderText(
  text: string,
  onCitationClick: (number: number) => void,
): React.ReactNode[] {
  const nodes: React.ReactNode[] = [];
  const pattern = /\[(\d+(?:\s*[–,]\s*\d+)*)\]/g;
  let lastIndex = 0;
  let match: RegExpExecArray | null;
  let key = 0;

  while ((match = pattern.exec(text)) !== null) {
    if (match.index > lastIndex) {
      nodes.push(text.slice(lastIndex, match.index));
    }
    const numbers = match[1]
      .split(/[–,]/)
      .map((part) => Number(part.trim()))
      .filter((value) => Number.isInteger(value));
    for (const number of numbers) {
      nodes.push(
        <button
          key={`cite-${key++}`}
          type="button"
          className="sg-cite"
          onClick={() => onCitationClick(number)}
        >
          [{number}]
        </button>,
      );
    }
    lastIndex = match.index + match[0].length;
  }
  if (lastIndex < text.length) {
    nodes.push(text.slice(lastIndex));
  }
  return nodes;
}

export default function ReaderPane({
  chunks,
  references,
  links,
}: {
  chunks: Chunk[];
  references: ReferenceEntry[];
  links: CitationLink[];
}) {
  const chapters = useMemo(() => buildChapters(chunks), [chunks]);
  const [activeRef, setActiveRef] = useState<number | null>(null);
  const [activeChunk, setActiveChunk] = useState<string | null>(null);
  const [selection, setSelection] = useState("");
  const [selectionChunk, setSelectionChunk] = useState<Chunk | null>(null);
  const chunkRefs = useRef<Record<string, HTMLElement | null>>({});

  const refsByNumber = useMemo(() => {
    const map = new Map<number, ReferenceEntry>();
    for (const ref of references) map.set(ref.number, ref);
    return map;
  }, [references]);

  const chunkById = useMemo(() => {
    const map = new Map<string, Chunk>();
    for (const chunk of chunks) map.set(chunk.chunk_id, chunk);
    return map;
  }, [chunks]);

  /** 点正文引用 → 跳到文末条目 */
  function jumpToReference(number: number) {
    setActiveRef(number);
    setActiveChunk(null);
    const element = document.getElementById(`ref-${number}`);
    if (element) {
      element.scrollIntoView({ behavior: "smooth", block: "center" });
    }
  }

  /** 点文末条目 → 跳回引用它的 Chunk */
  function jumpToCitation(number: number) {
    const target = links.find((link) => link.citation_number === number);
    setActiveRef(number);
    if (target) {
      setActiveChunk(target.chunk_id);
      const element = chunkRefs.current[target.chunk_id];
      if (element) {
        element.scrollIntoView({ behavior: "smooth", block: "center" });
      }
    } else {
      setActiveChunk(null);
    }
  }

  /** 划词：只展示原文与所属 Chunk 锚点，不生成译文 */
  function captureSelection(chunk: Chunk) {
    const selected = window.getSelection()?.toString().trim() ?? "";
    if (!selected) return;
    setSelection(selected);
    setSelectionChunk(chunk);
  }

  return (
    <div className="sg-reader">
      <aside className="sg-reader__nav">
        <h2 className="sg-section__title">章节导航</h2>
        <p className="sg-mono">
          {chapters.length} 个章节 · {chunks.length} 个分块
        </p>
        <ul className="sg-nav-list">
          {chapters.map((chapter) => (
            <li key={chapter.key}>
              <button
                type="button"
                className="sg-nav-item"
                onClick={() => {
                  const first = chapter.chunkIds[0];
                  if (!first) return;
                  setActiveChunk(first);
                  const element = chunkRefs.current[first];
                  if (element) {
                    element.scrollIntoView({
                      behavior: "smooth",
                      block: "start",
                    });
                  }
                }}
              >
                <span className="sg-nav-item__title">{chapter.title}</span>
                <span className="sg-mono">
                  p.{Math.min(...chapter.pages)} · {chapter.chunkIds.length} 块
                </span>
              </button>
            </li>
          ))}
        </ul>

        <h2 className="sg-section__title">文末条目</h2>
        <ul className="sg-nav-list">
          {references.map((ref) => (
            <li key={ref.ref_id}>
              <button
                type="button"
                id={`ref-${ref.number}`}
                className={
                  activeRef === ref.number
                    ? "sg-nav-item sg-nav-item--active"
                    : "sg-nav-item"
                }
                onClick={() => jumpToCitation(ref.number)}
              >
                <span className="sg-nav-item__title">
                  [{ref.number}] {ref.title ?? "（标题未提取）"}
                </span>
                <span className="sg-mono">
                  {ref.authors.join("; ")} · {ref.year ?? "—"} ·{" "}
                  {ref.venue ?? "—"}
                </span>
              </button>
            </li>
          ))}
        </ul>
      </aside>

      <div className="sg-reader__main">
        <div className="sg-note">
          <span className="sg-tag sg-tag--warning">
            版式原文渲染待后端文件端点
          </span>
          <p className="sg-note__text">
            后端没有提供 PDF 原文件下载端点，本页不渲染 PDF 版式原文，
            阅读材料为已落盘的 Chunk 正文。不凭空构造 PDF 接口。
          </p>
        </div>

        {chunks.map((chunk) => (
          <article
            key={chunk.chunk_id}
            id={chunk.chunk_id}
            ref={(element) => {
              chunkRefs.current[chunk.chunk_id] = element;
            }}
            className={
              activeChunk === chunk.chunk_id
                ? "sg-chunk sg-chunk--active"
                : "sg-chunk"
            }
            onMouseUp={() => captureSelection(chunk)}
          >
            <header className="sg-chunk__head">
              <span className="sg-mono">p.{chunk.page_number}</span>
              <span className="sg-mono">{chunk.chunk_id}</span>
              <span className="sg-tag">{chunk.type}</span>
            </header>
            {chunk.section_path.length > 0 ? (
              <p className="sg-mono">{chunk.section_path.join(" / ")}</p>
            ) : null}
            <p className="sg-prose">
              {renderText(chunk.text, jumpToReference)}
            </p>
          </article>
        ))}
      </div>

      <aside className="sg-reader__side">
        <h2 className="sg-section__title">划词</h2>
        {selection ? (
          <div className="sg-selection">
            <p className="sg-prose">{selection}</p>
            <p className="sg-mono">
              {selectionChunk
                ? `所属分块 p.${selectionChunk.page_number} · ${selectionChunk.chunk_id}`
                : "—"}
            </p>
            <div className="sg-note">
              <span className="sg-tag sg-tag--warning">
                翻译功能待后端模型接入
              </span>
              <p className="sg-note__text">
                后端目前没有翻译端点，本页只展示原文与所属 Chunk 锚点，
                不生成、不伪造任何译文。
              </p>
            </div>
          </div>
        ) : (
          <p className="sg-mono">
            用鼠标选中正文即可查看原文与所属分块锚点。
          </p>
        )}

        <h2 className="sg-section__title">引用对应关系</h2>
        {links.length === 0 ? (
          <p className="sg-mono">无引用对应记录。</p>
        ) : (
          <table className="sg-table">
            <thead>
              <tr>
                <th className="sg-num">引用</th>
                <th className="sg-num">页</th>
                <th>目标条目</th>
              </tr>
            </thead>
            <tbody>
              {links.map((link, index) => {
                const target = refsByNumber.get(link.citation_number);
                const chunk = chunkById.get(link.chunk_id);
                return (
                  <tr
                    key={`${link.citation_number}-${link.chunk_id}-${index}`}
                  >
                    <td className="sg-num">[{link.citation_number}]</td>
                    <td className="sg-num">{link.page_number}</td>
                    <td>
                      <button
                        type="button"
                        className="sg-linklike"
                        onClick={() => jumpToReference(link.citation_number)}
                      >
                        {target?.title ?? link.ref_id}
                      </button>
                      {chunk ? (
                        <div className="sg-mono">
                          p.{chunk.page_number} · {chunk.chunk_id}
                        </div>
                      ) : null}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </aside>
    </div>
  );
}

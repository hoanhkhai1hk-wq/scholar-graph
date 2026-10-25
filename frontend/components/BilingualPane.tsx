"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import type { TranslateSegment } from "@/lib/types";
import MarkdownView from "./MarkdownView";

/**
 * 中英双栏对照视图。
 *
 * 对齐口径（backend/README.md 第 283、291 行）：按 segments 的 source_chunk_id 匹配，
 * 与译文字符长度无关。两栏都由同一份 segments 顺序渲染，因此第 i 段互为对应段。
 *
 * 滚动同步：任一栏滚动/点击时，取该栏视口顶部最近的一段，把另一栏滚到同 id 的段。
 * 双向都通，用一个短暂的锁避免两栏互相触发。
 */
type Side = "left" | "right";

export default function BilingualPane({
  segments,
  markdown,
  markdownMode,
}: {
  segments: TranslateSegment[];
  markdown: string | null;
  markdownMode: boolean;
}) {
  const leftRef = useRef<HTMLDivElement>(null);
  const rightRef = useRef<HTMLDivElement>(null);
  const lockRef = useRef<Side | null>(null);
  const [activeId, setActiveId] = useState<string | null>(null);

  /** 取容器内视口顶部最近的段 */
  const topChunkId = useCallback((container: HTMLElement | null) => {
    if (!container) return null;
    const rows = container.querySelectorAll<HTMLElement>("[data-chunk-id]");
    if (rows.length === 0) return null;
    const top = container.getBoundingClientRect().top;
    let bestId: string | null = null;
    let bestDistance = Number.POSITIVE_INFINITY;
    rows.forEach((row) => {
      const distance = Math.abs(row.getBoundingClientRect().top - top);
      if (distance < bestDistance) {
        bestDistance = distance;
        bestId = row.dataset.chunkId ?? null;
      }
    });
    return bestId;
  }, []);

  /** 把目标栏滚到指定段 */
  const scrollToChunk = useCallback((container: HTMLElement | null, chunkId: string) => {
    if (!container) return;
    const target = container.querySelector<HTMLElement>(
      `[data-chunk-id="${CSS.escape(chunkId)}"]`,
    );
    if (!target) return;
    const containerTop = container.getBoundingClientRect().top;
    const targetTop = target.getBoundingClientRect().top;
    container.scrollTop += targetTop - containerTop - 8;
  }, []);

  const sync = useCallback(
    (from: Side) => {
      if (lockRef.current && lockRef.current !== from) return;
      lockRef.current = from;
      const source = from === "left" ? leftRef.current : rightRef.current;
      const target = from === "left" ? rightRef.current : leftRef.current;
      const chunkId = topChunkId(source);
      if (chunkId) {
        setActiveId(chunkId);
        scrollToChunk(target, chunkId);
      }
      window.setTimeout(() => {
        lockRef.current = null;
      }, 140);
    },
    [scrollToChunk, topChunkId],
  );

  function jump(from: Side, chunkId: string) {
    lockRef.current = from;
    setActiveId(chunkId);
    const target = from === "left" ? rightRef.current : leftRef.current;
    scrollToChunk(target, chunkId);
    window.setTimeout(() => {
      lockRef.current = null;
    }, 160);
  }

  useEffect(() => {
    setActiveId(segments[0]?.source_chunk_id ?? null);
  }, [segments]);

  if (segments.length === 0) {
    return <p className="sg-mono">没有可对照的段。</p>;
  }

  return (
    <div className="sg-bilingual">
      <div className="sg-bilingual__col">
        <h4 className="sg-qa__sub">英文原文</h4>
        <div
          className="sg-bilingual__scroll"
          ref={leftRef}
          onScroll={() => sync("left")}
        >
          {segments.map((segment) => (
            <article
              key={segment.source_chunk_id}
              data-chunk-id={segment.source_chunk_id}
              className={
                activeId === segment.source_chunk_id
                  ? "sg-seg sg-seg--active"
                  : "sg-seg"
              }
              onClick={() => jump("left", segment.source_chunk_id)}
            >
              <header className="sg-mono">
                p.{segment.page_number} · {segment.source_chunk_id.slice(-12)}
              </header>
              <p className="sg-prose">{segment.source_text}</p>
            </article>
          ))}
        </div>
      </div>

      <div className="sg-bilingual__col">
        <h4 className="sg-qa__sub">中文译文</h4>
        <div
          className="sg-bilingual__scroll"
          ref={rightRef}
          onScroll={() => sync("right")}
        >
          {markdownMode && markdown ? (
            <MarkdownView markdown={markdown} />
          ) : (
            segments.map((segment) => (
              <article
                key={segment.source_chunk_id}
                data-chunk-id={segment.source_chunk_id}
                className={
                  activeId === segment.source_chunk_id
                    ? "sg-seg sg-seg--active"
                    : "sg-seg"
                }
                onClick={() => jump("right", segment.source_chunk_id)}
              >
                <header className="sg-mono">
                  p.{segment.page_number} ·{" "}
                  {segment.source_chunk_id.slice(-12)}
                </header>
                <p className="sg-prose">{segment.translated_text}</p>
              </article>
            ))
          )}
        </div>
      </div>
    </div>
  );
}

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
  const [bottomAligned, setBottomAligned] = useState(false);

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

  /**
   * 把目标栏滚到指定段。
   * 触底补偿：目标段顶不到顶部（已滚到底）时，改为两栏一起按底部对齐，
   * 避免"一边到底、另一边还停在中间"的错配，并如实标注当前是底部对齐。
   */
  const scrollToChunk = useCallback(
    (container: HTMLElement | null, chunkId: string, both?: HTMLElement | null) => {
      if (!container) return;
      const target = container.querySelector<HTMLElement>(
        `[data-chunk-id="${CSS.escape(chunkId)}"]`,
      );
      if (!target) return;
      const containerTop = container.getBoundingClientRect().top;
      const targetTop = target.getBoundingClientRect().top;
      const before = container.scrollTop;
      container.scrollTop += targetTop - containerTop - 8;

      const maxScroll = container.scrollHeight - container.clientHeight;
      // 只要目标栏停在底部，就按底部对齐处理并把另一栏也带到底部。
      // 不要求"本次才到底"——否则紧随其后的滚动回调会把状态又清掉。
      if (container.scrollTop >= maxScroll - 1) {
        container.scrollTop = maxScroll;
        if (both) both.scrollTop = both.scrollHeight - both.clientHeight;
        setBottomAligned(true);
      } else {
        setBottomAligned(false);
      }
      void before;
    },
    [],
  );

  const sync = useCallback(
    (from: Side) => {
      if (lockRef.current && lockRef.current !== from) return;
      lockRef.current = from;
      const source = from === "left" ? leftRef.current : rightRef.current;
      const target = from === "left" ? rightRef.current : leftRef.current;
      const chunkId = topChunkId(source);
      if (chunkId) {
        setActiveId(chunkId);
        scrollToChunk(target, chunkId, source);
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
    const source = from === "left" ? leftRef.current : rightRef.current;
    scrollToChunk(target, chunkId, source);
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
      {bottomAligned ? (
        <p className="sg-mono">
          该段已到栏底，无法顶到顶部；两栏改为按底部对齐（触底补偿），
          对应段仍以高亮标出。
        </p>
      ) : null}
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

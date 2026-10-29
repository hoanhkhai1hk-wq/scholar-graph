"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import type { TranslateSegment } from "@/lib/types";
import MarkdownView from "./MarkdownView";
import AnchorTag from "./AnchorTag";
import { mapBilingualScroll } from "@/lib/bilingual-scroll";

/**
 * 中英双栏对照视图。
 *
 * 对齐口径（backend/README.md 第 283、291 行）：按 segments 的 source_chunk_id 匹配，
 * 与译文字符长度无关。两栏都由同一份 segments 顺序渲染，因此第 i 段互为对应段。
 *
 * 滚动同步：按相同段落边界插值映射段内进度，每帧最多更新一次。
 * 只忽略程序自己触发的位置回调，任一栏的真实输入均可立即接管。
 */
type Side = "left" | "right";

export default function BilingualPane({
  segments,
  markdown,
  markdownMode,
  target = "zh",
}: {
  segments: TranslateSegment[];
  markdown: string | null;
  markdownMode: boolean;
  target?: string;
}) {
  const leftRef = useRef<HTMLDivElement>(null);
  const rightRef = useRef<HTMLDivElement>(null);
  const frameRef = useRef<number | null>(null);
  const pendingRef = useRef<Side>("left");
  const expectedRef = useRef<Partial<Record<Side, number>>>({});
  const [activeId, setActiveId] = useState<string | null>(null);
  const [bottomAligned, setBottomAligned] = useState(false);

  /**
   * 把目标栏滚到指定段。
   * 对照栏到边界时标明限制，保留当前阅读栏位置。
   */
  const scrollToChunk = useCallback(
    (container: HTMLElement | null, chunkId: string) => {
      if (!container) return;
      const target = container.querySelector<HTMLElement>(
        `[data-chunk-id="${CSS.escape(chunkId)}"]`,
      );
      if (!target) return;
      const containerTop = container.getBoundingClientRect().top;
      const targetTop = target.getBoundingClientRect().top;
      container.scrollTop += targetTop - containerTop - 8;

      const maxScroll = container.scrollHeight - container.clientHeight;
      if (container.scrollTop >= maxScroll - 1) {
        container.scrollTop = maxScroll;
        setBottomAligned(true);
      } else {
        setBottomAligned(false);
      }
    },
    [],
  );

  const sync = useCallback(
    (from: Side) => {
      const source = from === "left" ? leftRef.current : rightRef.current;
      if (!source) return;
      const expected = expectedRef.current[from];
      if (expected !== undefined && Math.abs(source.scrollTop - expected) <= 1) {
        delete expectedRef.current[from]; return;
      }
      delete expectedRef.current[from];
      pendingRef.current = from;
      if (frameRef.current !== null) return;
      frameRef.current = requestAnimationFrame(() => {
        frameRef.current = null;
        const side = pendingRef.current, other = side === "left" ? "right" : "left";
        const origin = side === "left" ? leftRef.current : rightRef.current;
        const destination = side === "left" ? rightRef.current : leftRef.current;
        if (!origin || !destination) return;
        const anchors = (container: HTMLElement) => [...container.querySelectorAll<HTMLElement>("[data-chunk-id]")].map(row => ({ id: row.dataset.chunkId!, top: row.getBoundingClientRect().top - container.getBoundingClientRect().top - container.clientTop + container.scrollTop }));
        const mapped = mapBilingualScroll(origin.scrollTop, origin.scrollHeight - origin.clientHeight, destination.scrollHeight - destination.clientHeight, anchors(origin), anchors(destination));
        setActiveId(mapped.id); setBottomAligned(mapped.atBottom);
        // Suppress only the exact scroll caused by this assignment. A new user
        // scroll on either column takes ownership immediately, without a timer.
        expectedRef.current[other] = mapped.top;
        destination.scrollTop = mapped.top;
        expectedRef.current[other] = destination.scrollTop;
      });
    },
    [],
  );

  function jump(from: Side, chunkId: string) {
    setActiveId(chunkId);
    const target = from === "left" ? rightRef.current : leftRef.current;
    const other = from === "left" ? "right" : "left";
    scrollToChunk(target, chunkId);
    if (target) expectedRef.current[other] = target.scrollTop;
  }

  useEffect(() => {
    setActiveId(segments[0]?.source_chunk_id ?? null);
    expectedRef.current = {};
    if (leftRef.current) leftRef.current.scrollTop = 0;
    if (rightRef.current) rightRef.current.scrollTop = 0;
  }, [segments]);

  useEffect(() => () => { if (frameRef.current !== null) cancelAnimationFrame(frameRef.current); }, []);

  if (segments.length === 0) {
    return <p className="sg-mono">没有可对照的段。</p>;
  }

  return (
    <div className="sg-bilingual">
      {bottomAligned ? (
        <p className="sg-mono">
          对照栏已到边界；对应段仍以高亮标出，当前阅读栏的位置保持不变。
        </p>
      ) : null}
      <div className="sg-bilingual__col">
        <h4 className="sg-qa__sub">{target === "en" ? "中文原文" : "英文原文"}</h4>
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
                第 {segment.page_number} 页
              </header>
              <p className="sg-prose sg-source-text">{segment.source_text}</p>
              <AnchorTag anchor={{ paper_id: segment.paper_id, chunk_id: segment.source_chunk_id, page_number: segment.page_number, section: segment.section_path }} />
            </article>
          ))}
        </div>
      </div>

      <div className="sg-bilingual__col">
        <h4 className="sg-qa__sub">{target === "en" ? "英文译文" : "中文译文"}</h4>
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
                  第 {segment.page_number} 页
                </header>
                <p className="sg-prose sg-source-text">{segment.translated_text}</p>
              </article>
            ))
          )}
        </div>
      </div>
    </div>
  );
}

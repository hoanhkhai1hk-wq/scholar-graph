"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import type { Chunk, CitationLink, ReferenceEntry } from "@/lib/types";

type PdfPage = {
  getViewport: (opts: { scale: number }) => { width: number; height: number };
  render: (opts: { canvasContext: CanvasRenderingContext2D; viewport: unknown }) => {
    promise: Promise<void>;
  };
  cleanup: () => Promise<void>;
};

type PdfDoc = {
  numPages: number;
  getPage: (n: number) => Promise<PdfPage>;
  destroy: () => Promise<void>;
};

interface TreeNode {
  path: string[];
  label: string;
  page: number;
  children: TreeNode[];
}

/** 用已解析章节结构生成标题树：每个节点的页码取该路径下最早出现的物理页 */
function buildTree(chunks: Chunk[]): TreeNode[] {
  const roots: TreeNode[] = [];

  for (const chunk of chunks) {
    if (chunk.section_path.length === 0) continue;
    let level = roots;
    let prefix: string[] = [];

    for (const part of chunk.section_path) {
      prefix = [...prefix, part];
      let node = level.find((item) => item.label === part);
      if (!node) {
        node = {
          path: prefix,
          label: part,
          page: chunk.page_number,
          children: [],
        };
        level.push(node);
      } else {
        node.page = Math.min(node.page, chunk.page_number);
      }
      level = node.children;
    }
  }

  const sortTree = (nodes: TreeNode[]) => {
    nodes.sort((a, b) => a.page - b.page || a.label.localeCompare(b.label));
    for (const node of nodes) sortTree(node.children);
  };
  sortTree(roots);
  return roots;
}

/**
 * 版式原文阅读器（pdf.js）。
 *
 * 三条口径：
 * 1. 渲染的是文件端点返回的 **PDF 原件**，不是解析后的 Markdown，也不重排版面；
 * 2. 标题树与参考文献跳转都是**页级精度**——跳到该页的画布，做不到字符级定位；
 * 3. 没有对应页的条目如实说明，不猜页码，不跳转到近似位置。
 */
export default function LayoutViewer({
  paperId,
  chunks,
  references,
  links,
}: {
  paperId: string;
  chunks: Chunk[];
  references: ReferenceEntry[];
  links: CitationLink[];
}) {
  const [status, setStatus] = useState<"loading" | "ok" | "error">("loading");
  const [message, setMessage] = useState<string | null>(null);
  const [numPages, setNumPages] = useState<number | null>(null);
  const [currentPage, setCurrentPage] = useState(1);
  const [activeRef, setActiveRef] = useState<string | null>(null);

  const canvasHostRef = useRef<HTMLDivElement>(null);
  const docRef = useRef<PdfDoc | null>(null);
  const renderedRef = useRef<Set<number>>(new Set());
  const pageRefs = useRef<Map<number, HTMLElement>>(new Map());
  const refItemRefs = useRef<Map<string, HTMLElement>>(new Map());

  const tree = useMemo(() => buildTree(chunks), [chunks]);

  /** 每个参考文献条 → 正文中引用它的页码（按 ref_id ↔ CitationLink 对应） */
  const pagesByRefId = useMemo(() => {
    const map = new Map<string, number[]>();
    for (const link of links) {
      const list = map.get(link.ref_id) ?? [];
      if (!list.includes(link.page_number)) list.push(link.page_number);
      map.set(link.ref_id, list.sort((a, b) => a - b));
    }
    return map;
  }, [links]);

  /** 当前页上出现的引用编号 → 对应的文献条目，用于从 PDF 页回到文献列表 */
  const refsOnPage = useMemo(() => {
    const map = new Map<number, { ref_id: string; number: number }[]>();
    for (const link of links) {
      const ref = references.find((item) => item.ref_id === link.ref_id);
      if (!ref) continue;
      const list = map.get(link.page_number) ?? [];
      if (!list.some((item) => item.ref_id === link.ref_id)) {
        list.push({ ref_id: link.ref_id, number: ref.number });
      }
      map.set(link.page_number, list.sort((a, b) => a.number - b.number));
    }
    return map;
  }, [links, references]);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        const pdfjs = await import("pdfjs-dist");
        pdfjs.GlobalWorkerOptions.workerSrc = "/pdf.worker.min.mjs";

        const response = await fetch(`/api/backend/papers/${paperId}/file`, {
          headers: { accept: "application/pdf" },
        });
        if (!response.ok) {
          let detail = `HTTP ${response.status}`;
          try {
            const parsed = (await response.json()) as { message?: string };
            if (parsed.message) detail = `${parsed.message}（HTTP ${response.status}）`;
          } catch {
            // 保留 HTTP 状态作为说明
          }
          throw new Error(detail);
        }
        const data = await response.arrayBuffer();

        if (cancelled) return;
        const task = pdfjs.getDocument({ data });
        const doc = (await task.promise) as unknown as PdfDoc;
        docRef.current = doc;
        setNumPages(doc.numPages);
        setStatus("ok");
        // 先量出每页高度并占位，再谈跳转：
        // 否则未渲染的页高度为 0，标题树跳到第 N 页后，上方页面陆续渲染变高，
        // 会把目标页推下去，跳到的页数就不对了。
        void measureAllPages(doc, doc.numPages);
      } catch (cause) {
        if (cancelled) return;
        setStatus("error");
        setMessage(
          cause instanceof Error
            ? cause.message
            : "版式原文加载失败，未用其他内容冒充。",
        );
      }
    }

    void load();

    return () => {
      cancelled = true;
      void docRef.current?.destroy();
      docRef.current = null;
      renderedRef.current.clear();
    };
  }, [paperId]);

  /** 量出每页高度占位（长书按序渐进，量完即释放该页对象） */
  async function measureAllPages(doc: PdfDoc, total: number) {
    for (let index = 1; index <= total; index += 1) {
      if (!docRef.current) return;
      const page = await doc.getPage(index);
      const viewport = page.getViewport({ scale: 1.4 });
      const height = Math.floor(viewport.height);
      const element = pageRefs.current.get(index);
      if (element) {
        element.style.minHeight = `${height + 44}px`;
        element.dataset.measured = "1";
      }
      await page.cleanup();
    }
  }

  /** 懒渲染：页面进入视口才画，避免长书一次画几百张画布 */
  useEffect(() => {
    if (status !== "ok" || !numPages) return;
    const host = canvasHostRef.current;
    if (!host) return;

    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (!entry.isIntersecting) continue;
          const element = entry.target as HTMLElement;
          const page = Number(element.dataset.page);
          if (renderedRef.current.has(page)) continue;
          renderedRef.current.add(page);
          void renderPage(page, element);
        }
      },
      { rootMargin: "400px 0px" },
    );

    host.querySelectorAll<HTMLElement>("[data-page]").forEach((element) => {
      observer.observe(element);
    });

    return () => observer.disconnect();

    async function renderPage(page: number, host: HTMLElement) {
      const doc = docRef.current;
      if (!doc) return;
      const canvas = host.querySelector("canvas");
      if (!canvas) return;
      const pageProxy = await doc.getPage(page);
      const viewport = pageProxy.getViewport({ scale: 1.4 });
      canvas.width = Math.floor(viewport.width);
      canvas.height = Math.floor(viewport.height);
      canvas.style.width = "100%";
      canvas.style.height = "auto";
      const context = canvas.getContext("2d");
      if (!context) return;
      await pageProxy.render({ canvasContext: context, viewport }).promise;
    }
  }, [status, numPages]);

  /** 跟踪当前可见页（取视口顶部最近的一页） */
  useEffect(() => {
    const host = canvasHostRef.current;
    if (!host) return;
    const observer = new IntersectionObserver(
      (entries) => {
        const visible = entries
          .filter((entry) => entry.isIntersecting)
          .map((entry) => Number((entry.target as HTMLElement).dataset.page));
        if (visible.length > 0) {
          setCurrentPage(Math.min(...visible));
        }
      },
      { rootMargin: "-20% 0px -70% 0px" },
    );
    host.querySelectorAll<HTMLElement>("[data-page]").forEach((element) => {
      observer.observe(element);
    });
    return () => observer.disconnect();
  }, [status, numPages]);

  /**
   * 跳页：先把目标页**及它之前所有页**的高度量出来占位，再滚动。
   * 只量目标页不够——上方页面陆续量到真实高度后会把目标页顶下去，
   * 于是"跳第 7 页"会落到第 6 页。量完后再补一次校正滚动，抵消后台量高造成的位移。
   */
  async function scrollToPage(page: number) {
    const element = pageRefs.current.get(page);
    if (!element) return;
    const doc = docRef.current;

    if (doc) {
      for (let index = 1; index <= page; index += 1) {
        const target = pageRefs.current.get(index);
        if (!target || target.dataset.measured) continue;
        const pdfPage = await doc.getPage(index);
        const viewport = pdfPage.getViewport({ scale: 1.4 });
        target.style.minHeight = `${Math.floor(viewport.height) + 44}px`;
        target.dataset.measured = "1";
        await pdfPage.cleanup();
      }
    }

    element.scrollIntoView({ behavior: "auto", block: "start" });
    setCurrentPage(page);
    requestAnimationFrame(() => {
      element.scrollIntoView({ behavior: "auto", block: "start" });
      setCurrentPage(page);
    });
  }

  /** 点参考文献 → 跳到它在正文中的引用页 */
  function jumpToCitation(refId: string) {
    const pages = pagesByRefId.get(refId);
    setActiveRef(refId);
    if (!pages || pages.length === 0) return;
    scrollToPage(pages[0]);
  }

  /** 从当前 PDF 页 → 回到该条参考文献（滚动并高亮） */
  function jumpToReference(refId: string) {
    setActiveRef(refId);
    const element = refItemRefs.current.get(refId);
    if (element) {
      element.scrollIntoView({ behavior: "smooth", block: "center" });
    }
  }

  if (status === "loading") {
    return <p className="sg-mono">正在载入 PDF 原件…</p>;
  }

  if (status === "error") {
    return (
      <div className="sg-note">
        <span className="sg-tag sg-tag--error">版式原文不可用</span>
        <p className="sg-note__text">
          {message}
          。后端未保留原件时返回 404；此处不改用解析文本或 Markdown 冒充版式原文。
        </p>
      </div>
    );
  }

  const onPageRefs = refsOnPage.get(currentPage) ?? [];

  return (
    <div className="sg-layout">
      <aside className="sg-layout__nav">
        <h2 className="sg-section__title">标题树（页级定位）</h2>
        <p className="sg-mono">
          按已解析 section_path 生成，页码为该章节首个 Chunk 的 PDF 物理页。
        </p>
        <ul className="sg-nav-list">
          {tree.map((node) => (
            <TreeItem key={node.path.join("/")} node={node} onJump={scrollToPage} />
          ))}
        </ul>

        <h2 className="sg-section__title">参考文献（点条跳到引用页）</h2>
        <ul className="sg-nav-list">
          {references.map((ref) => {
            const pages = pagesByRefId.get(ref.ref_id) ?? [];
            return (
              <li key={ref.ref_id}>
                <button
                  type="button"
                  ref={(element) => {
                    if (element) refItemRefs.current.set(ref.ref_id, element);
                  }}
                  className={
                    activeRef === ref.ref_id
                      ? "sg-nav-item sg-nav-item--active"
                      : "sg-nav-item"
                  }
                  onClick={() => jumpToCitation(ref.ref_id)}
                >
                  <span className="sg-nav-item__title">
                    [{ref.number}] {ref.title ?? "（标题未提取）"}
                  </span>
                  <span className="sg-mono">
                    {pages.length > 0
                      ? `正文中引用出现在 p.${pages.join("、p.")}`
                      : "正文引用位置未解析出，无法跳转"}
                  </span>
                </button>
              </li>
            );
          })}
        </ul>
      </aside>

      <div className="sg-layout__main">
        <div className="sg-layout__bar">
          <span className="sg-mono">
            共 {numPages} 页 · 当前第 {currentPage} 页
          </span>
          {onPageRefs.length > 0 ? (
            <span className="sg-layout__backrefs">
              本页引用：
              {onPageRefs.map((item) => (
                <button
                  key={item.ref_id}
                  type="button"
                  className="sg-linklike"
                  onClick={() => jumpToReference(item.ref_id)}
                >
                  [{item.number}]
                </button>
              ))}
              （点击回到该条参考文献）
            </span>
          ) : (
            <span className="sg-mono">本页没有解析出的正文引用标记</span>
          )}
        </div>

        <div className="sg-layout__pages" ref={canvasHostRef}>
          {Array.from({ length: numPages ?? 0 }, (_, index) => index + 1).map(
            (page) => (
              <section
                key={page}
                id={`pdf-page-${page}`}
                data-page={page}
                ref={(element) => {
                  if (element) pageRefs.current.set(page, element);
                }}
                className={
                  currentPage === page
                    ? "sg-pdfpage sg-pdfpage--active"
                    : "sg-pdfpage"
                }
              >
                <header className="sg-mono">第 {page} 页</header>
                <canvas />
              </section>
            ),
          )}
        </div>

        <p className="sg-mono">
          以上为文件端点返回的 PDF 原件逐页渲染（pdf.js），单栏/双栏以原件为准；
          不是解析后的 Markdown，也不重新排版。标题树与参考文献跳转均为**页级精度**：
          只能定位到该页，做不到字符级定位。
        </p>
      </div>
    </div>
  );
}

function TreeItem({
  node,
  onJump,
  depth = 0,
}: {
  node: TreeNode;
  onJump: (page: number) => void;
  depth?: number;
}) {
  return (
    <li>
      <button
        type="button"
        className="sg-nav-item"
        style={{ paddingLeft: `${8 + depth * 14}px` }}
        onClick={() => onJump(node.page)}
      >
        <span className="sg-nav-item__title">{node.label}</span>
        <span className="sg-mono">p.{node.page}</span>
      </button>
      {node.children.length > 0 ? (
        <ul className="sg-nav-list">
          {node.children.map((child) => (
            <TreeItem
              key={child.path.join("/")}
              node={child}
              onJump={onJump}
              depth={depth + 1}
            />
          ))}
        </ul>
      ) : null}
    </li>
  );
}

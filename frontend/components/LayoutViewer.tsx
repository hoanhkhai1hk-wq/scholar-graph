"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import type { Chunk, CitationLink, ReferenceEntry } from "@/lib/types";

type TextItem = { str: string; transform: number[]; width: number; height: number };

type PdfPage = {
  getViewport: (opts: { scale: number }) => {
    width: number;
    height: number;
    transform: number[];
  };
  render: (opts: { canvasContext: CanvasRenderingContext2D; viewport: unknown }) => {
    promise: Promise<void>;
  };
  getTextContent: (opts?: { normalizeWhitespace?: boolean }) => Promise<{
    items: TextItem[];
  }>;
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
  queries: string[];
  children: TreeNode[];
}

interface Highlight {
  page: number;
  x: number;
  y: number;
  w: number;
  h: number;
}

const SCALE = 1.4;
/** 未量到真实高度前的占位比例（A4 附近），量到后替换 */
const DEFAULT_RATIO = 1.32;

function snippetOf(text: string, length = 48): string {
  return text.replace(/\s+/g, " ").trim().slice(0, length);
}

function applyTransform(m: number[], x: number, y: number): [number, number] {
  return [m[0] * x + m[2] * y + m[4], m[1] * x + m[3] * y + m[5]];
}

/** 用已解析 Chunk 的 section_path 生成标题树，并带上文本层定位用的候选串 */
function buildTree(chunks: Chunk[]): TreeNode[] {
  const roots: TreeNode[] = [];
  const firstByPath = new Map<string, { page: number; text: string }>();

  for (const chunk of chunks) {
    if (chunk.section_path.length === 0) continue;
    let prefix: string[] = [];
    for (const part of chunk.section_path) {
      prefix = [...prefix, part];
      const key = prefix.join(" / ");
      const existing = firstByPath.get(key);
      if (!existing || chunk.page_number < existing.page) {
        firstByPath.set(key, { page: chunk.page_number, text: chunk.text });
      }
    }
  }

  for (const [key, value] of firstByPath) {
    const parts = key.split(" / ");
    let level = roots;
    let node: TreeNode | null = null;

    for (let depth = 0; depth < parts.length; depth += 1) {
      const part = parts[depth];
      const found = level.find((item) => item.label === part);
      if (found) {
        node = found;
      } else {
        node = {
          path: parts.slice(0, depth + 1),
          label: part,
          page: value.page,
          queries: [part, snippetOf(value.text)],
          children: [],
        };
        level.push(node);
      }
      node.page = Math.min(node.page, value.page);
      level = node.children;
    }
  }

  const sortTree = (nodes: TreeNode[]) => {
    nodes.sort((a, b) => a.page - b.page || a.label.localeCompare(b.label));
    for (const item of nodes) sortTree(item.children);
  };
  sortTree(roots);
  return roots;
}

/**
 * 版式原文阅读器（pdf.js）。
 *
 * 定位精度口径：
 * 1. 优先**段落级定位**：在 PDF 文本层搜到该段文字，滚过去并高亮命中区间；
 * 2. 文本层搜不到（扫描件、文字转曲、chunk 与 PDF 文本不一致）时退回**页级定位**
 *    并在界面写明，不假装定位到段落；
 * 3. 字符级坐标定位做不到，未实现，也不声称能定位到某一行或某个字。
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
  const [highlight, setHighlight] = useState<Highlight | null>(null);
  const [locateNote, setLocateNote] = useState<string | null>(null);
  const [timing, setTiming] = useState<{ load: number; first: number } | null>(null);

  const canvasHostRef = useRef<HTMLDivElement>(null);
  const docRef = useRef<PdfDoc | null>(null);
  const renderedRef = useRef<Set<number>>(new Set());
  const pageRefs = useRef<Map<number, HTMLElement>>(new Map());
  const refItemRefs = useRef<Map<string, HTMLElement>>(new Map());
  const startRef = useRef<number>(0);
  const firstPaintRef = useRef(false);

  const tree = useMemo(() => buildTree(chunks), [chunks]);
  const chunkById = useMemo(() => {
    const map = new Map<string, Chunk>();
    for (const chunk of chunks) map.set(chunk.chunk_id, chunk);
    return map;
  }, [chunks]);

  const linksByRefId = useMemo(() => {
    const map = new Map<string, CitationLink[]>();
    for (const link of links) {
      const list = map.get(link.ref_id) ?? [];
      list.push(link);
      map.set(link.ref_id, list);
    }
    return map;
  }, [links]);

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
    startRef.current = performance.now();

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
        setTiming({ load: performance.now() - startRef.current, first: 0 });
        setStatus("ok");
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

  /** 未量高前按 A4 附近比例占位，避免未渲染页高度为 0 导致跳页偏移 */
  function ensurePlaceholder(page: number) {
    const element = pageRefs.current.get(page);
    if (!element || element.dataset.measured === "1") return;
    const width = element.clientWidth || 700;
    element.style.minHeight = `${Math.round(width * DEFAULT_RATIO) + 60}px`;
  }

  /** 按需量高：只量进入视口附近的页，不一次性量完 541 页 */
  async function measurePage(page: number): Promise<void> {
    const element = pageRefs.current.get(page);
    const doc = docRef.current;
    if (!element || !doc || element.dataset.measured === "1") return;
    const pdfPage = await doc.getPage(page);
    const viewport = pdfPage.getViewport({ scale: SCALE });
    const width = element.clientWidth || 700;
    const ratio = viewport.height / viewport.width;
    element.style.minHeight = `${Math.round(width * ratio) + 60}px`;
    element.dataset.measured = "1";
    await pdfPage.cleanup();
  }

  async function renderPage(page: number, host: HTMLElement) {
    const doc = docRef.current;
    if (!doc) return;
    const canvas = host.querySelector("canvas");
    if (!canvas) return;
    const pdfPage = await doc.getPage(page);
    const viewport = pdfPage.getViewport({ scale: SCALE });
    canvas.width = Math.floor(viewport.width);
    canvas.height = Math.floor(viewport.height);
    canvas.style.width = "100%";
    canvas.style.height = "auto";
    const context = canvas.getContext("2d");
    if (!context) {
      await pdfPage.cleanup();
      return;
    }
    await pdfPage.render({ canvasContext: context, viewport }).promise;
    await pdfPage.cleanup();
    if (!firstPaintRef.current) {
      firstPaintRef.current = true;
      setTiming((value) => ({
        load: value?.load ?? 0,
        first: performance.now() - startRef.current,
      }));
    }
  }

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
          void (async () => {
            await measurePage(page);
            if (renderedRef.current.has(page)) return;
            renderedRef.current.add(page);
            await renderPage(page, element);
          })();
        }
      },
      { rootMargin: "600px 0px" },
    );

    host.querySelectorAll<HTMLElement>("[data-page]").forEach((element) => {
      const page = Number(element.dataset.page);
      ensurePlaceholder(page);
      observer.observe(element);
    });

    return () => observer.disconnect();
  }, [status, numPages]);

  useEffect(() => {
    const host = canvasHostRef.current;
    if (!host) return;
    const observer = new IntersectionObserver(
      (entries) => {
        const visible = entries
          .filter((entry) => entry.isIntersecting)
          .map((entry) => Number((entry.target as HTMLElement).dataset.page));
        if (visible.length > 0) setCurrentPage(Math.min(...visible));
      },
      { rootMargin: "-20% 0px -70% 0px" },
    );
    host.querySelectorAll<HTMLElement>("[data-page]").forEach((element) => {
      observer.observe(element);
    });
    return () => observer.disconnect();
  }, [status, numPages]);

  function scrollToPageOffset(page: number, offsetY: number) {
    const element = pageRefs.current.get(page);
    if (!element) return;
    const go = () => {
      const top = element.getBoundingClientRect().top + window.scrollY + (offsetY || 0) - 90;
      window.scrollTo({ top: Math.max(0, top), behavior: "auto" });
    };
    go();
    requestAnimationFrame(() => {
      go();
      setCurrentPage(page);
      // 量高/渲染可能改变上方页高度，再补一次校正
      window.setTimeout(go, 260);
    });
    setCurrentPage(page);
  }

  /** 在页面文本层里搜候选串，返回命中区间（已换算到画布 CSS 坐标） */
  async function locateInPage(
    page: number,
    queries: string[],
  ): Promise<Omit<Highlight, "page"> | null> {
    const doc = docRef.current;
    const host = pageRefs.current.get(page);
    if (!doc || !host) return null;

    const pdfPage = await doc.getPage(page);
    const viewport = pdfPage.getViewport({ scale: SCALE });
    const content = await pdfPage.getTextContent({ normalizeWhitespace: true });
    const items = content.items ?? [];

    let raw = "";
    for (const item of items) raw += item.str ?? "";
    let normalized = "";
    const origin: number[] = [];
    let pendingSpace = false;
    for (let i = 0; i < raw.length; i += 1) {
      const ch = raw[i];
      if (/\s/.test(ch)) {
        if (normalized.length > 0) pendingSpace = true;
        continue;
      }
      if (pendingSpace) {
        normalized += " ";
        origin.push(i);
        pendingSpace = false;
      }
      normalized += ch.toLowerCase();
      origin.push(i);
    }

    let matched: { start: number; end: number } | null = null;
    for (const query of queries) {
      const needle = query.replace(/\s+/g, " ").trim().toLowerCase();
      if (needle.length < 4) continue;
      const at = normalized.indexOf(needle);
      if (at >= 0) {
        matched = { start: origin[at], end: origin[at + needle.length - 1] };
        break;
      }
    }
    if (!matched) {
      await pdfPage.cleanup();
      return null;
    }

    let base = 0;
    let minX = Infinity;
    let minY = Infinity;
    let maxX = -Infinity;
    let maxY = -Infinity;
    for (const item of items) {
      const len = (item.str ?? "").length;
      const start = base;
      const end = base + len - 1;
      base += len;
      if (end < matched.start || start > matched.end) continue;
      const [, , , , px, py] = item.transform;
      const [x, y] = applyTransform(viewport.transform, px, py);
      const width = (item.width ?? 0) * SCALE;
      const height = (item.height ?? 10) * SCALE;
      minX = Math.min(minX, x);
      maxX = Math.max(maxX, x + width);
      minY = Math.min(minY, y - height);
      maxY = Math.max(maxY, y + height * 0.3);
    }
    await pdfPage.cleanup();

    if (!Number.isFinite(minX)) return null;
    const canvas = host.querySelector("canvas");
    const ratio = canvas && canvas.width ? canvas.clientWidth / canvas.width : 1;
    return {
      x: minX * ratio,
      y: minY * ratio,
      w: Math.max(24, (maxX - minX) * ratio),
      h: Math.max(14, (maxY - minY) * ratio),
    };
  }

  async function locateAndJump(page: number, queries: string[], label: string) {
    setLocateNote(null);
    setHighlight(null);
    const element = pageRefs.current.get(page);
    if (element && !renderedRef.current.has(page)) {
      await measurePage(page);
      renderedRef.current.add(page);
      await renderPage(page, element);
    }
    const hit = await locateInPage(page, queries);
    if (hit) {
      setHighlight({ page, ...hit });
      setLocateNote(`段落级定位：第 ${page} 页文本层命中「${label}」，已滚动并高亮。`);
      scrollToPageOffset(page, hit.y);
    } else {
      setLocateNote(
        `段落级定位未命中：第 ${page} 页文本层没找到「${label}」，已退回页首（页级定位）。`,
      );
      scrollToPageOffset(page, 0);
    }
  }

  function jumpToCitation(refId: string) {
    setActiveRef(refId);
    const entries = linksByRefId.get(refId) ?? [];
    const ref = references.find((item) => item.ref_id === refId);
    if (entries.length === 0) {
      setLocateNote("该条没有解析出正文引用位置，无法跳转。");
      return;
    }
    const link = entries[0];
    const chunk = chunkById.get(link.chunk_id);
    void locateAndJump(
      link.page_number,
      [`[${ref?.number ?? ""}]`, chunk ? snippetOf(chunk.text) : ""],
      `文献 [${ref?.number ?? "?"}] 的引用处`,
    );
  }

  function backToReference(refId: string) {
    setActiveRef(refId);
    const element = refItemRefs.current.get(refId);
    if (element) element.scrollIntoView({ behavior: "smooth", block: "center" });
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
        <h3 className="sg-qa__sub">标题树（段落级定位）</h3>
        <p className="sg-mono">
          点标题会在 PDF 文本层搜索该段文字并高亮；搜不到时退回页首并写明。
        </p>
        <ul className="sg-nav-list">
          {tree.map((node) => (
            <TreeItem
              key={node.path.join("/")}
              node={node}
              onJump={(page, queries) => locateAndJump(page, queries, node.label)}
            />
          ))}
        </ul>

        <h3 className="sg-qa__sub">参考文献（点条跳到引用处）</h3>
        <ul className="sg-nav-list">
          {references.map((ref) => {
            const entries = linksByRefId.get(ref.ref_id) ?? [];
            const pages = [
              ...new Set(entries.map((item) => item.page_number)),
            ].sort((a, b) => a - b);
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
                      ? `正文引用出现在 p.${pages.join("、p.")}`
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
          {timing ? (
            <span className="sg-mono">
              载入 {timing.load.toFixed(0)} ms
              {timing.first > 0 ? ` · 首屏渲染 ${timing.first.toFixed(0)} ms` : ""}
            </span>
          ) : null}
          {onPageRefs.length > 0 ? (
            <span className="sg-layout__backrefs">
              本页引用：
              {onPageRefs.map((item) => (
                <button
                  key={item.ref_id}
                  type="button"
                  className="sg-linklike"
                  onClick={() => backToReference(item.ref_id)}
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

        {locateNote ? (
          <p className="sg-mono sg-layout__note">{locateNote}</p>
        ) : null}

        <div className="sg-layout__pages" ref={canvasHostRef}>
          {Array.from({ length: numPages ?? 0 }, (_, index) => index + 1).map((page) => (
            <section
              key={page}
              id={`pdf-page-${page}`}
              data-page={page}
              ref={(element) => {
                if (element) pageRefs.current.set(page, element);
              }}
              className={
                currentPage === page ? "sg-pdfpage sg-pdfpage--active" : "sg-pdfpage"
              }
            >
              <header className="sg-mono">第 {page} 页</header>
              <div className="sg-pdfpage__stage">
                <canvas />
                {highlight && highlight.page === page ? (
                  <span
                    className="sg-pdfpage__hit"
                    style={{
                      left: `${highlight.x}px`,
                      top: `${highlight.y}px`,
                      width: `${highlight.w}px`,
                      height: `${highlight.h}px`,
                    }}
                  />
                ) : null}
              </div>
            </section>
          ))}
        </div>

        <p className="sg-mono">
          以上为文件端点返回的 PDF 原件逐页渲染（pdf.js），单栏/双栏以原件为准；
          不是解析后的 Markdown，也不重新排版。定位为段落级：在文本层搜到该段文字后滚动
          并高亮；搜不到时退回页首并如实写明。字符级坐标定位未实现。
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
  onJump: (page: number, queries: string[]) => void;
  depth?: number;
}) {
  return (
    <li>
      <button
        type="button"
        className="sg-nav-item"
        style={{ paddingLeft: `${8 + depth * 14}px` }}
        onClick={() => onJump(node.page, node.queries)}
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

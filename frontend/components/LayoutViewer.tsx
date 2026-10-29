"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import type { Chunk, CitationLink, ReferenceEntry } from "@/lib/types";
import AsyncStatus from "./AsyncStatus";

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
  onPageChange,
  onSelection,
  hoverTranslation = false,
  bibliographyLocations = {},
  outlineChunks,
}: {
  paperId: string;
  chunks: Chunk[];
  references: ReferenceEntry[];
  links: CitationLink[];
  onPageChange?: (page: number) => void;
  onSelection?: (selection: { text: string; page: number; kind: "selection" | "hover" }) => void;
  hoverTranslation?: boolean;
  bibliographyLocations?: Record<string, { page_number: number; chunk_id: string; text: string }>;
  outlineChunks?: Chunk[];
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
  const retainedPages = useRef<Set<number>>(new Set());
  const renderTasks = useRef<Map<number, { cancel: () => void }>>(new Map());
  const renderPromises = useRef<Map<number, Promise<void>>>(new Map());
  const pageRefs = useRef<Map<number, HTMLElement>>(new Map());
  const refItemRefs = useRef<Map<string, HTMLElement>>(new Map());
  const startRef = useRef<number>(0);
  const firstPaintRef = useRef(false);
  const restoredRef = useRef(false);
  const hoverTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const citationOrigin = useRef<Map<string, { page: number; top: number }>>(new Map());
  const [jumpInput, setJumpInput] = useState("");

  const tree = useMemo(() => buildTree(outlineChunks ?? chunks), [outlineChunks, chunks]);
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

        if (cancelled) return;
        const task = pdfjs.getDocument({ url: `/api/backend/papers/${paperId}/file`, rangeChunkSize: 65536, disableAutoFetch: true, disableStream: true });
        const doc = (await task.promise) as unknown as PdfDoc;
        if (cancelled) { await doc.destroy(); return; }
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
      retainedPages.current.clear();
      for (const task of renderTasks.current.values()) task.cancel();
      renderTasks.current.clear();
      if (hoverTimer.current) clearTimeout(hoverTimer.current);
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
    if (!retainedPages.current.has(page) || docRef.current !== doc) { await pdfPage.cleanup(); return; }
    const viewport = pdfPage.getViewport({ scale: SCALE });
    const width = element.clientWidth || 700;
    const ratio = viewport.height / viewport.width;
    element.dataset.pageRatio = String(ratio);
    element.style.minHeight = `${Math.round(width * ratio) + 60}px`;
    element.dataset.measured = "1";
    await pdfPage.cleanup();
  }

  function renderPage(page: number, host: HTMLElement): Promise<void> {
    const active = renderPromises.current.get(page);
    if (active) return active.then(() => {
      // A page can re-enter while its earlier cancelled draw is still settling.
      // Serialize the new draw after cancellation instead of leaving a blank canvas.
      if (retainedPages.current.has(page) && host.dataset.rendered !== "true") return renderPage(page, host);
    });
    const job = drawPage(page, host).finally(() => renderPromises.current.delete(page));
    renderPromises.current.set(page, job);
    return job;
  }

  async function drawPage(page: number, host: HTMLElement) {
    const doc = docRef.current;
    if (!doc) return;
    const canvas = host.querySelector("canvas");
    if (!canvas) return;
    const pdfPage = await doc.getPage(page);
    if (!retainedPages.current.has(page) || docRef.current !== doc) { renderedRef.current.delete(page); await pdfPage.cleanup(); return; }
    const viewport = pdfPage.getViewport({ scale: SCALE });
    canvas.width = Math.floor(viewport.width);
    canvas.height = Math.floor(viewport.height);
    canvas.style.width = "100%";
    canvas.style.height = "auto";
    const context = canvas.getContext("2d");
    if (!context) {
      renderedRef.current.delete(page);
      await pdfPage.cleanup();
      return;
    }
    const task = pdfPage.render({ canvasContext: context, viewport });
    renderTasks.current.set(page, task as typeof task & { cancel: () => void });
    try { await task.promise; }
    catch (cause) { renderedRef.current.delete(page); if (!(cause instanceof Error) || cause.name !== "RenderingCancelledException") setLocateNote("该页绘制未完成，请重新定位到此页重试。"); return; }
    finally { renderTasks.current.delete(page); }
    if (!retainedPages.current.has(page)) { canvas.width = 0; canvas.height = 0; renderedRef.current.delete(page); await pdfPage.cleanup(); return; }
    const layer = host.querySelector<HTMLElement>(".sg-pdf-text");
    if (layer) {
      const pdfjs = await import("pdfjs-dist");
      layer.replaceChildren();
      layer.style.width = `${viewport.width}px`;
      layer.style.height = `${viewport.height}px`;
      layer.style.transform = `scale(${canvas.clientWidth / viewport.width})`;
      layer.style.setProperty("--scale-factor", String(SCALE));
      await new pdfjs.TextLayer({ textContentSource: await pdfPage.getTextContent() as never, container: layer, viewport: viewport as never }).render();
      // PDF text runs often split brackets and digits into separate spans.
      // Map matches back to the original digit glyphs; keep all source text and punctuation.
      const numbers = new Set((refsOnPage.get(page) ?? []).map(item => item.number));
      const spans = [...layer.querySelectorAll("span")].filter(span => !span.childElementCount);
      const runs = spans.map(span => ({ span, text: span.textContent ?? "", start: 0 }));
      let full = "";
      for (const run of runs) { run.start = full.length; full += run.text; }
      const marks: { start: number; end: number; refId: string; number: number }[] = [];
      for (const match of full.matchAll(/\[\s*\d+(?:\s*[,;–-]\s*\d+)*\s*\]/g)) {
        for (const token of match[0].matchAll(/\d+/g)) {
          const number = Number(token[0]), ref = references.find(item => item.number === number);
          if (ref && numbers.has(number)) marks.push({ start: match.index! + token.index!, end: match.index! + token.index! + token[0].length, refId: ref.ref_id, number });
        }
      }
      for (const run of runs) {
        const local = marks.filter(mark => mark.start < run.start + run.text.length && mark.end > run.start);
        if (!local.length) continue;
        const fragment = document.createDocumentFragment(); let cursor = 0;
        for (const mark of local) {
          const start = Math.max(0, mark.start - run.start), end = Math.min(run.text.length, mark.end - run.start);
          fragment.append(run.text.slice(cursor, start));
          const button = document.createElement("button"); button.type = "button"; button.textContent = run.text.slice(start, end);
          button.dataset.referenceId = mark.refId; button.setAttribute("aria-label", `查看参考文献 ${mark.number}`);
          button.title = `查看参考文献 ${mark.number}`; fragment.append(button); cursor = end;
        }
        fragment.append(run.text.slice(cursor)); run.span.replaceChildren(fragment);
      }
    }
    await pdfPage.cleanup();
    if (!retainedPages.current.has(page)) { canvas.width = 0; canvas.height = 0; layer?.replaceChildren(); renderedRef.current.delete(page); return; }
    host.dataset.rendered = "true";
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
          if (!entry.isIntersecting) {
            const element = entry.target as HTMLElement;
            retainedPages.current.delete(Number(element.dataset.page));
            const canvas = element.querySelector("canvas");
            if (canvas) {
              renderTasks.current.get(Number(element.dataset.page))?.cancel();
              canvas.width = 0; canvas.height = 0;
              delete element.dataset.rendered;
              element.querySelector(".sg-pdf-text")?.replaceChildren();
              renderedRef.current.delete(Number(element.dataset.page));
            }
            continue;
          }
          const element = entry.target as HTMLElement;
          const page = Number(element.dataset.page);
          retainedPages.current.add(page);
          void (async () => {
            await measurePage(page);
            if (!retainedPages.current.has(page)) return;
            if (element.dataset.rendered === "true") return;
            renderedRef.current.add(page);
            await renderPage(page, element);
          })();
        }
      },
      { root: host.closest("[data-document-scroll]"), rootMargin: "600px 0px" },
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
    if (!host || status !== "ok") return;
    let previousWidth = host.clientWidth;
    const observer = new ResizeObserver(() => {
      // Hidden mobile panes have width zero. Re-measuring their page placeholders
      // would collapse the whole book and shift the saved scroll position.
      if (!host.clientWidth || host.clientWidth === previousWidth) return;
      previousWidth = host.clientWidth;
      host.querySelectorAll<HTMLElement>("[data-page]").forEach(element => {
        const canvas = element.querySelector("canvas"), layer = element.querySelector<HTMLElement>(".sg-pdf-text");
        const ratio = Number(element.dataset.pageRatio || DEFAULT_RATIO);
        element.style.minHeight = `${Math.round(element.clientWidth * ratio) + 60}px`;
        if (canvas && canvas.width && layer) layer.style.transform = `scale(${canvas.clientWidth / canvas.width})`;
      });
      setHighlight(null);
    });
    observer.observe(host); return () => observer.disconnect();
  }, [status, numPages]);

  useEffect(() => {
    if (status !== "ok" || !numPages || restoredRef.current) return;
    restoredRef.current = true;
    const params = new URLSearchParams(window.location.search);
    const page = Math.min(numPages, Math.max(1, Number(params.get("page") || localStorage.getItem(`sg.reading.${paperId}`) || 1)));
    const chunkId = params.get("chunk");
    if (chunkId) void fetch(`/api/workspace/papers/${paperId}/evidence/${encodeURIComponent(chunkId)}`).then(async response => {
      if (!response.ok) throw new Error("证据段落未找到，已定位到指定页。");
      const chunk = await response.json() as Chunk;
      await locateAndJump(chunk.page_number, [snippetOf(chunk.text)], "答案证据");
    }).catch(() => { void locateAndJump(page, [], "指定页"); });
    else if (page > 1) void locateAndJump(page, [], "上次阅读位置");
  }, [status, numPages, paperId]);

  useEffect(() => {
    if (status !== "ok") return;
    onPageChange?.(currentPage);
    if (restoredRef.current) localStorage.setItem(`sg.reading.${paperId}`, String(currentPage));
  }, [currentPage, status, paperId, onPageChange]);

  useEffect(() => {
    const locate = (event: Event) => {
      const anchor = (event as CustomEvent<{ chunk_id: string; page_number: number }>).detail;
      void fetch(`/api/workspace/papers/${paperId}/evidence/${encodeURIComponent(anchor.chunk_id)}`).then(async response => {
        if (!response.ok) throw new Error();
        const chunk = await response.json() as Chunk;
        await locateAndJump(chunk.page_number, [snippetOf(chunk.text)], "答案证据");
      }).catch(() => { void locateAndJump(anchor.page_number, [], "证据页"); });
    };
    window.addEventListener("sg:locate", locate);
    return () => window.removeEventListener("sg:locate", locate);
  }, [paperId, status]);

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
      { root: host.closest("[data-document-scroll]"), rootMargin: "-20% 0px -70% 0px" },
    );
    host.querySelectorAll<HTMLElement>("[data-page]").forEach((element) => {
      observer.observe(element);
    });
    return () => observer.disconnect();
  }, [status, numPages]);

  function scrollToPageOffset(page: number, offsetY: number, restoreTop?: number) {
    const element = pageRefs.current.get(page);
    if (!element) return;
    const go = () => {
      const container = element.closest<HTMLElement>("[data-document-scroll]");
      if (container) container.scrollTo({ top: restoreTop ?? element.getBoundingClientRect().top - container.getBoundingClientRect().top + container.scrollTop + (offsetY || 0) - 64, behavior: "auto" });
      else window.scrollTo({ top: Math.max(0, element.getBoundingClientRect().top + window.scrollY + (offsetY || 0) - 90), behavior: "auto" });
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
    for (let i = 0; i < raw.length; i += 1) {
      for (const ch of raw[i].normalize("NFKC").toLowerCase()) {
        // PDF text layers retain printed line-break hyphens (architec-ture),
        // while parsed source paragraphs join those words. Ignore hyphens in
        // both search strings, retaining origin offsets for actual highlights.
        if (/[\s\u00ad\-\u2010\u2011]/.test(ch)) continue;
        normalized += ch; origin.push(i);
      }
    }

    let matched: { start: number; end: number } | null = null;
    for (const query of queries) {
      const needle = query.normalize("NFKC").replace(/[\s\u00ad\-\u2010\u2011]/g, "").toLowerCase();
      if (needle.length < 4 && !/^\[\d+\]$/.test(needle)) continue;
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

  async function locateAndJump(page: number, queries: string[], label: string, restoreTop?: number) {
    setLocateNote(null);
    setHighlight(null);
    const element = pageRefs.current.get(page);
    // Bring the target into the retained page window before drawing it.
    scrollToPageOffset(page, 0, restoreTop);
    if (element) {
      retainedPages.current.add(page);
      await measurePage(page);
      if (!renderedRef.current.has(page) || renderPromises.current.has(page)) {
        renderedRef.current.add(page); await renderPage(page, element);
      }
      if (element.dataset.rendered !== "true") {
        renderedRef.current.add(page); await renderPage(page, element);
      }
    }
    const hit = await locateInPage(page, queries);
    if (hit) {
      setHighlight({ page, ...hit });
      setLocateNote(`段落级定位：第 ${page} 页文本层命中「${label}」，已滚动并高亮。`);
      scrollToPageOffset(page, hit.y, restoreTop);
    } else {
      setLocateNote(
        `段落级定位未命中：第 ${page} 页文本层没找到「${label}」，已退回页首（页级定位）。`,
      );
      scrollToPageOffset(page, 0, restoreTop);
    }
    return !!hit;
  }

  async function citationQueries(refId: string, page: number) {
    const entry = (linksByRefId.get(refId) ?? []).find(link => link.page_number === page);
    let chunk = entry ? chunkById.get(entry.chunk_id) : undefined;
    if (!chunk && entry) {
      try {
        const response = await fetch(`/api/workspace/papers/${paperId}/evidence/${encodeURIComponent(entry.chunk_id)}`);
        if (response.ok) chunk = await response.json() as Chunk;
      } catch { /* An exact citation marker can still locate the reference. */ }
    }
    const ref = references.find(item => item.ref_id === refId);
    return [`[${ref?.number ?? ""}]`, chunk ? snippetOf(chunk.text) : ""];
  }

  async function jumpToCitation(refId: string) {
    setActiveRef(refId);
    const entries = linksByRefId.get(refId) ?? [];
    const ref = references.find((item) => item.ref_id === refId);
    if (entries.length === 0) {
      setLocateNote("该条没有解析出正文引用位置，无法跳转。");
      return;
    }
    const origin = citationOrigin.current.get(refId);
    if (origin) {
      const queries = await citationQueries(refId, origin.page);
      const hit = await locateAndJump(origin.page, queries, `文献 [${ref?.number}] 的引用处`, origin.top);
      setLocateNote(`已返回第 ${origin.page} 页刚才的引用位置；${hit ? "原文已重新高亮" : "文本未命中，仅恢复页和阅读位置"}。`);
      return;
    }
    const link = entries[0];
    void locateAndJump(
      link.page_number,
      await citationQueries(refId, link.page_number),
      `文献 [${ref?.number ?? "?"}] 的引用处`,
    );
  }

  function backToReference(refId: string, sourcePage = currentPage) {
    const container = canvasHostRef.current?.closest<HTMLElement>("[data-document-scroll]");
    citationOrigin.current.set(refId, { page: sourcePage, top: container?.scrollTop ?? window.scrollY });
    setActiveRef(refId);
    const reference = references.find(item => item.ref_id === refId);
    const location = reference ? bibliographyLocations[String(reference.number)] : undefined;
    if (location) {
      void locateAndJump(location.page_number, [snippetOf(location.text)], `参考文献 [${reference?.number}]`);
      return;
    }
    const element = refItemRefs.current.get(refId);
    if (element) element.scrollIntoView({ behavior: "smooth", block: "center" });
    setLocateNote("文末物理位置未提取，已打开文献条目；原文位置已保存，可返回。");
  }

  if (status === "loading") {
    return <div className="sg-pdf-loading"><AsyncStatus label="正在载入 PDF 原件…" rows={8} /></div>;
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
      <aside id="paper-outline" className="sg-layout__nav" aria-label="本篇目录与参考文献">
        <h3 className="sg-qa__sub">标题树（段落级定位）</h3>
        <p className="sg-mono">
          点标题会在 PDF 文本层搜索该段文字并高亮；搜不到时退回页首并写明。
        </p>
        <ul className="sg-nav-list">
          {tree.map((node) => (
            <TreeItem
              key={node.path.join("/")}
              node={node}
              onJump={(page, queries, label) => locateAndJump(page, queries, label)}
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
          <label className="sg-field">跳页<input className="sg-input sg-input--narrow" type="number" min={1} max={numPages ?? 1} value={jumpInput} onChange={event => setJumpInput(event.target.value)} aria-label="跳转页码" /></label>
          <button className="sg-btn sg-btn--ghost" onClick={() => { const page = Number(jumpInput); if (Number.isInteger(page) && page >= 1 && page <= (numPages ?? 1)) void locateAndJump(page, [], "指定页"); }}>前往</button>
          {activeRef && citationOrigin.current.has(activeRef) ? <button className="sg-btn sg-btn--ghost" onClick={() => jumpToCitation(activeRef)}>返回刚才引用处</button> : null}
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

        <div className="sg-layout__pages" ref={canvasHostRef} onClick={event => {
          const button = (event.target as HTMLElement).closest<HTMLElement>("[data-reference-id]");
          if (button?.dataset.referenceId) backToReference(button.dataset.referenceId, Number(button.closest<HTMLElement>("[data-page]")?.dataset.page) || currentPage);
        }} onMouseUp={event => {
          const selection = window.getSelection();
          const text = selection?.toString().trim();
          const host = (event.target as HTMLElement).closest<HTMLElement>("[data-page]");
          if (text && host && text.length <= 4000) onSelection?.({ text, page: Number(host.dataset.page), kind: "selection" });
        }} onMouseMove={event => {
          if (hoverTimer.current) clearTimeout(hoverTimer.current);
          if (!hoverTranslation || window.getSelection()?.toString().trim()) return;
          const target = event.target as HTMLElement;
          if (!target.closest(".sg-pdf-text")) return;
          const host = target.closest<HTMLElement>("[data-page]");
          const range = (document as Document & { caretRangeFromPoint?: (x: number, y: number) => Range | null }).caretRangeFromPoint?.(event.clientX, event.clientY);
          if (!range || !host) return;
          const text = range.startContainer.textContent ?? "";
          let left = range.startOffset, right = range.startOffset;
          while (left > 0 && /[A-Za-z'-]/.test(text[left - 1])) left--;
          while (right < text.length && /[A-Za-z'-]/.test(text[right])) right++;
          const word = text.slice(left, right);
          if (word.length >= 2 && word.length < 60) hoverTimer.current = setTimeout(() => onSelection?.({ text: word, page: Number(host.dataset.page), kind: "hover" }), 800);
        }} onMouseLeave={() => { if (hoverTimer.current) clearTimeout(hoverTimer.current); }}>
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
                <canvas width={0} height={0} />
                <div className="sg-pdf-text" />
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

        <details className="sg-diag"><summary>原文显示与定位说明</summary><p className="sg-mono">
          以上为文件端点返回的 PDF 原件逐页渲染（pdf.js），单栏/双栏以原件为准；
          不是解析后的 Markdown，也不重新排版。定位为段落级：在文本层搜到该段文字后滚动
          并高亮；搜不到时退回页首并如实写明。字符级坐标定位未实现。
        </p></details>
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
  onJump: (page: number, queries: string[], label: string) => void;
  depth?: number;
}) {
  return (
    <li>
      <button
        type="button"
        className="sg-nav-item"
        style={{ paddingLeft: `${8 + depth * 14}px` }}
        onClick={() => onJump(node.page, node.queries, node.label)}
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

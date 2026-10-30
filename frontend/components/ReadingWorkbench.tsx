"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { Chunk, TranslateResponse } from "@/lib/types";
import { getReading, workspacePost, type ReadingContext } from "@/lib/workspace";
import LayoutViewer from "./LayoutViewer";
import ReaderPane from "./ReaderPane";
import ResearchChat from "./ResearchChat";
import TranslatePanel from "./TranslatePanel";
import StructureInspector from "./StructureInspector";
import AsyncStatus from "./AsyncStatus";

export default function ReadingWorkbench({ initial }: { initial: ReadingContext }) {
  const [context, setContext] = useState(initial);
  const [view, setView] = useState<"pdf" | "text" | "translation" | "structure">("pdf");
  const [assistantOpen, setAssistantOpen] = useState(true);
  const [outlineOpen, setOutlineOpen] = useState(false);
  const [hoverTranslation, setHoverTranslation] = useState(false);
  const [selection, setSelection] = useState<{ text: string; page: number; kind: "selection" | "hover" } | null>(null);
  const [translation, setTranslation] = useState("");
  const [translating, setTranslating] = useState(false);
  const [error, setError] = useState("");
  const [pageLoading, setPageLoading] = useState(false);
  useEffect(() => {
    const screen = matchMedia("(max-width: 1100px)");
    const update = () => { const stored = localStorage.getItem("sg.reader.assistant"); setAssistantOpen(stored === null ? !screen.matches : stored === "open"); };
    update(); screen.addEventListener("change", update);
    return () => screen.removeEventListener("change", update);
  }, []);
  function toggleAssistant() { const next = !assistantOpen; setAssistantOpen(next); localStorage.setItem("sg.reader.assistant", next ? "open" : "closed"); }
  const paper = initial.paper;
  const pageRequest = useRef(0);
  const currentContext = useRef(initial);
  const pendingPages = useRef(new Map<number, Promise<ReadingContext>>());
  const outlineChunks = useMemo<Chunk[]>(() => initial.outline.map(item => ({ ...item, schema_version: "1.0.0", paper_id: paper.id, heading_1: item.section_path[0] ?? null, heading_2: item.section_path[1] ?? null, heading_3: item.section_path[2] ?? null, bbox: null, type: "text" })), [initial, paper.id]);
  const navigationChunks = useMemo(() => [...new Map([...outlineChunks, ...context.chunks].map(chunk => [chunk.chunk_id, chunk])).values()], [outlineChunks, context.chunks]);
  const pageChanged = useCallback(async (page: number) => {
    const request = ++pageRequest.current;
    // The initial physical page already came with the server-rendered document.
    // Do not immediately fetch that same page again when pdf.js becomes ready.
    if (currentContext.current.page_number === page) { setPageLoading(false); return currentContext.current; }
    setPageLoading(true);
    try {
      let pending = pendingPages.current.get(page);
      if (!pending) { pending = getReading(paper.id, page, false); pendingPages.current.set(page, pending); }
      const value = await pending;
      if (request === pageRequest.current) { currentContext.current = value; setContext(value); return value; }
    } catch (cause) { if (request === pageRequest.current) setError(cause instanceof Error ? cause.message : "该页解析材料加载失败。"); }
    finally { pendingPages.current.delete(page); if (request === pageRequest.current) setPageLoading(false); }
  }, [paper.id]);

  async function translate(value = selection) {
    if (!value || translating) return;
    setTranslating(true); setTranslation(""); setError("");
    try {
      const response = await workspacePost<{ translation: TranslateResponse }>(`/papers/${paper.id}/translate-selection`, { text: value.text, page_number: value.page });
      setTranslation(response.translation.segments.map(segment => segment.translated_text).join("\n\n"));
    } catch (cause) { setError(cause instanceof Error ? cause.message : "选区翻译失败。"); }
    finally { setTranslating(false); }
  }

  function selected(value: { text: string; page: number; kind: "selection" | "hover" }) {
    if (translating || (selection?.text === value.text && selection.page === value.page)) return;
    setSelection(value); setTranslation(""); setError("");
    if (value.kind === "hover") void translate(value);
  }

  return <main className="sg-shell sg-shell--wide" onClickCapture={event => {
    if (event.defaultPrevented || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
    const link = (event.target as HTMLElement).closest<HTMLAnchorElement>("a.sg-anchor-inline");
    if (!link) return;
    const url = new URL(link.href);
    if (url.pathname !== `/read/${paper.id}`) return;
    event.preventDefault(); setView("pdf");
    window.history.replaceState(window.history.state, "", url.pathname + url.search);
    window.setTimeout(() => window.dispatchEvent(new CustomEvent("sg:locate", { detail: { chunk_id: url.searchParams.get("chunk"), page_number: Number(url.searchParams.get("page")) } })), 100);
  }}>
    <div className="sg-page-head"><p className="sg-mono"><Link href="/">论文库</Link> / 阅读研究</p><h1 className="sg-title">{paper.title ?? paper.arxiv_id ?? "论文阅读"}</h1><p className="sg-lede">{paper.authors.join("、") || "作者信息待补齐"} · {paper.page_count} 页 · {initial.total_chunks} 个正文段落</p></div>
    <div className="sg-reader-tabs" role="tablist" aria-label="阅读方式">{([['pdf', '原版式'], ['text', '本页文本'], ['translation', '双语与翻译'], ['structure', '信息与解析']] as const).map(([key, label]) => <button key={key} role="tab" aria-selected={view === key} onClick={() => { setView(key); if (key === "pdf" && matchMedia("(max-width: 1100px)").matches) { setAssistantOpen(false); setOutlineOpen(false); } }}>{label}</button>)}{view !== "translation" && view !== "structure" ? <button aria-expanded={assistantOpen} aria-controls="research-assistant" onClick={toggleAssistant}>{assistantOpen ? "收起研究助手" : "打开研究助手"}</button> : null}{view === "pdf" ? <button className="sg-reader-outline-toggle" aria-expanded={outlineOpen} aria-controls="paper-outline" onClick={() => { setOutlineOpen(!outlineOpen); setAssistantOpen(false); }}>{outlineOpen ? "收起目录" : "展开目录"}</button> : null}{view === "pdf" ? <label className="sg-checkbox"><input type="checkbox" checked={hoverTranslation} onChange={event => setHoverTranslation(event.target.checked)} />悬停翻译（停留后调用模型）</label> : null}</div>
    <div className={`sg-reader-workbench${!assistantOpen || view === "translation" || view === "structure" ? " is-wide" : ""}`} data-assistant-open={assistantOpen && view !== "translation" && view !== "structure"}>
      <div className="sg-reader-document" data-document-scroll data-outline-open={outlineOpen}>
        {view === "pdf" ? <LayoutViewer hasTextLayer={paper.has_text_layer} paperId={paper.id} chunks={navigationChunks} outlineChunks={outlineChunks} references={initial.references} links={initial.citation_links} bibliographyLocations={initial.bibliography_locations} onPageChange={pageChanged} onSelection={selected} hoverTranslation={hoverTranslation} /> : null}
        {view === "text" ? <><label className="sg-field">当前页<input type="number" className="sg-input sg-input--narrow" aria-label="文本页码" min={1} max={paper.page_count ?? 1} value={context.page_number} onChange={event => { const page = Number(event.target.value); if (page >= 1 && page <= (paper.page_count ?? 1)) pageChanged(page); }} /></label>{pageLoading ? <AsyncStatus label="正在读取该页正文…" rows={3} /> : null}<ReaderPane chunks={context.chunks} references={initial.references} links={initial.citation_links} onSelection={selected} onNavigate={(page, chunkId) => { void pageChanged(page).then(value => { if (value) requestAnimationFrame(() => document.getElementById(chunkId)?.scrollIntoView({ block: "center" })); }); }} /></> : null}
        {view === "structure" ? <StructureInspector paperId={paper.id} /> : null}
        {view === "translation" ? <section className="sg-section"><TranslatePanel paperId={paper.id} chunks={navigationChunks} pageCount={paper.page_count ?? 1} /></section> : null}
        {selection && view !== "translation" ? <div className="sg-inline-selection"><div className="sg-chat__actions"><strong>{selection.kind === "hover" ? "悬停翻译" : "选区翻译"} · 第 {selection.page} 页</strong><button className="sg-btn sg-btn--ghost" onClick={() => { setSelection(null); setTranslation(""); setError(""); }}>关闭</button></div><p className="sg-prose">{selection.text.slice(0, 500)}{selection.text.length > 500 ? "…" : ""}</p>{translation ? <p className="sg-prose">{translation}</p> : <button className="sg-btn" disabled={translating} onClick={() => void translate()}>{translating ? "正在翻译…" : "翻译选中文字"}</button>}{error ? <p role="alert">{error}</p> : null}</div> : null}
      </div>
      {assistantOpen && view !== "translation" && view !== "structure" ? <aside id="research-assistant" className="sg-research-assistant" aria-label="论文研究助手"><h2 className="sg-section__title">研究助手</h2><ResearchChat papers={[paper]} initialPaperIds={[paper.id]} compact /></aside> : null}
    </div>
    {error && !selection ? <p className="sg-error" role="alert">{error}</p> : null}
  </main>;
}

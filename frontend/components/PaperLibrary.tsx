"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import { getPaperViews, workspacePost, workspaceRequest, type PaperView } from "@/lib/workspace";
import type { Paged } from "@/lib/types";
import VersionResolution from "./VersionResolution";
import EmptyState from "./EmptyState";
import AsyncStatus from "./AsyncStatus";

export default function PaperLibrary() {
  const searchQuery = useSearchParams().get("q") ?? "";
  const [focused, setFocused] = useState("");
  const previewTrigger = useRef<HTMLButtonElement | null>(null), previewScroll = useRef(0);
  useEffect(() => { setQuery(searchQuery); setPage(1); }, [searchQuery]);
  const [data, setData] = useState<Paged<PaperView> | null>(null);
  const [query, setQuery] = useState(""); const [page, setPage] = useState(1); const [trash, setTrash] = useState(false);
  const [error, setError] = useState(""); const [loading, setLoading] = useState(true); const [busy, setBusy] = useState("");
  const [editing, setEditing] = useState<PaperView | null>(null); const [deleting, setDeleting] = useState<PaperView | null>(null);
  const dialog = useRef<HTMLDialogElement>(null);
  const [notice, setNotice] = useState("");
  const generation = useRef(0);
  const load = useCallback(async () => {
    const current = ++generation.current; setLoading(true);
    try { const value = await getPaperViews(`?page=${page}&page_size=20&archived=${trash}&title=${encodeURIComponent(query)}`); if (generation.current === current) { setData(value); setError(""); } }
    catch (cause) { if (generation.current === current) setError(cause instanceof Error ? cause.message : "论文库加载失败。"); }
    finally { if (generation.current === current) setLoading(false); }
  }, [page, trash, query]);
  useEffect(() => { const timer = setTimeout(() => void load(), 250); return () => clearTimeout(timer); }, [load]);
  useEffect(() => { if ((editing || deleting) && !dialog.current?.open) dialog.current?.showModal(); }, [editing, deleting]);
  async function action(view: PaperView, kind: "restore" | "delete" | "enrich") {
    setBusy(view.paper.id); setError(""); setNotice("");
    try {
      if (kind === "delete") await workspaceRequest(`/papers/${view.paper.id}`, { method: "DELETE" });
      else { const result = await workspacePost<{ enrichment_notice?: string }>(`/papers/${view.paper.id}/${kind}`, {}); if (kind === "enrich") setNotice(result.enrichment_notice ?? "已取得原文提取结果，请核对信息与缺失项。"); }
      setDeleting(null); dialog.current?.close(); await load();
    } catch (cause) { setError(cause instanceof Error ? cause.message : "操作未完成。"); }
    finally { setBusy(""); }
  }
  const preview = data?.items.find(view => view.paper.id === focused) ?? data?.items[0];
  function showPreview(view: PaperView, button: HTMLButtonElement) {
    previewTrigger.current = button; previewScroll.current = window.scrollY; setFocused(view.paper.id);
    if (matchMedia("(max-width: 760px)").matches) requestAnimationFrame(() => {
      const pane = document.getElementById("paper-preview"); pane?.scrollIntoView({ block: "start" }); pane?.focus({ preventScroll: true });
    });
  }
  return <main className="sg-shell"><div className="sg-page-head"><h1 className="sg-title">论文库</h1><p className="sg-lede">收藏研究材料，读懂原文，让每个问题都有可查的依据。</p><div className="sg-form"><Link href="/upload" className="sg-btn">上传论文</Link><Link href="/qa" className="sg-btn sg-btn--ghost">跨篇研究</Link></div></div>
    <div className="sg-library-controls"><input id="library-search" className="sg-input" type="search" aria-label="搜索论文" placeholder="搜索论文标题" value={query} onChange={event => { setQuery(event.target.value); setPage(1); }} /><button className="sg-btn sg-btn--ghost" aria-pressed={trash} onClick={() => { setTrash(!trash); setPage(1); }}>{trash ? "返回论文库" : "回收站"}</button><button className="sg-btn sg-btn--ghost" disabled={loading} onClick={load}>刷新</button></div>
    {error ? <div className="sg-error" role="alert"><p>{error}</p><div className="sg-form"><button className="sg-btn sg-btn--ghost" onClick={load}>重试读取论文库</button><Link href="/settings">检查服务状态</Link></div></div> : null}
    {notice ? <p role="status" className="sg-note">{notice}</p> : null}
    {loading && !data ? <AsyncStatus label="正在读取论文材料…" rows={6} /> : loading ? <p role="status">正在更新，暂时保留上一次结果。</p> : null}
    {data ? <><div className="sg-library-workbench"><section className="sg-library-materials" aria-label="论文材料列表"><p className="sg-paper-card__meta">{trash ? "回收站" : "论文库"} · 共 {data.total} 篇</p><div className="sg-card-list">{data.items.map(view => <article className={`sg-paper-card${preview?.paper.id === view.paper.id ? " is-previewed" : ""}`} key={view.paper.id}><div className="sg-paper-card__body"><h2 className="sg-paper-card__title"><Link href={`/read/${view.paper.id}`}>{view.paper.title || view.paper.arxiv_id || `信息待补齐的论文 · ${view.paper.page_count} 页`}</Link></h2><p className="sg-paper-card__meta">{view.paper.authors.slice(0, 4).join("、") || "作者信息待补齐"}{view.paper.authors.length > 4 ? ` 等 ${view.paper.authors.length} 位作者` : ""}</p>{view.paper.authors.length > 4 ? <details className="sg-paper-authors"><summary>查看全部作者（原文顺序）</summary><p className="sg-paper-card__meta">{view.paper.authors.join("、")}</p></details> : null}<p className="sg-paper-card__meta">{view.paper.year ?? "年份待补齐"} · {view.paper.page_count} 页{view.paper.version ? ` · ${view.paper.version}` : ""} · {view.paper.has_text_layer ? "文本 PDF" : "扫描 PDF"}</p>{view.missing_fields.length ? <span className="sg-tag sg-tag--warning">基础信息待补齐</span> : <span className="sg-tag sg-tag--success">基础信息已提取</span>}</div><div className="sg-paper-card__actions">{trash ? <button className="sg-btn" disabled={busy === view.paper.id} onClick={() => void action(view, "restore")}>恢复论文</button> : <><Link href={`/read/${view.paper.id}`} className="sg-btn sg-btn--text">阅读原文</Link><Link href={`/qa?paper=${view.paper.id}`} className="sg-btn sg-btn--text">提问</Link><button className="sg-btn sg-btn--ghost" aria-pressed={preview?.paper.id === view.paper.id} aria-controls="paper-preview" onClick={event => showPreview(view, event.currentTarget)}>预览材料</button></>}</div>{!trash ? <details className="sg-paper-actions"><summary>管理论文</summary><div className="sg-paper-management"><button className="sg-btn sg-btn--ghost" onClick={() => setEditing(view)}>编辑信息</button>{(view.missing_fields.length || !view.author_profiles.length) ? <button className="sg-btn sg-btn--ghost" disabled={busy === view.paper.id} onClick={() => void action(view, "enrich")}>{busy === view.paper.id ? "原文提取中…" : "补齐信息"}</button> : null}<VersionResolution paperId={view.paper.id} onResolved={load} /><button className="sg-btn sg-btn--danger" onClick={() => setDeleting(view)}>移入回收站</button></div><details className="sg-diag"><summary>来源信息</summary><p>{view.paper.source}</p>{view.year_source === "arxiv_submission_identifier" ? <p>年份依据原文 arXiv 编号的首次提交月份，代表预印本年份。</p> : null}<p className="sg-mono">{view.paper.id}</p><p>信息来源：{view.source === "user_correction" ? "人工修正" : view.source === "grobid_enrichment" ? "原文结构提取" : "初始解析"}</p></details></details> : null}</article>)}</div>{!data.items.length && !loading ? <EmptyState variant={query ? "search" : "library"} title={trash ? "回收站为空" : query ? "没有匹配的论文" : "你的第一篇论文，从这里开始"} hint={trash ? "移入回收站的论文会显示在这里，可以恢复原件与历史。" : query ? "换一个标题关键词，或清除条件查看全部材料。" : "上传 PDF，即可阅读原文、翻译和围绕材料提问。也可从顶部检索入口查找公开论文。"} action={query ? <button className="sg-btn sg-btn--ghost" onClick={() => setQuery("")}>清除搜索条件</button> : !trash ? <Link href="/upload" className="sg-btn">上传第一篇论文</Link> : undefined} /> : null}<div className="sg-pagination"><button className="sg-btn sg-btn--ghost" disabled={page <= 1 || loading} onClick={() => setPage(page - 1)}>上一页</button><span>第 {data.total_pages ? data.page : 0} / {data.total_pages} 页</span><button className="sg-btn sg-btn--ghost" disabled={!data.has_next || loading} onClick={() => setPage(page + 1)}>下一页</button></div></section>
    {preview ? <aside id="paper-preview" tabIndex={-1} className="sg-library-preview" aria-label="论文预览"><div className="sg-preview-sheet"><p className="sg-preview-label">当前材料 · 原文摘要</p><h3>{preview.paper.title ?? "标题信息待补齐"}</h3><p className="sg-paper-card__meta">{preview.paper.year ?? "年份待补齐"} · {preview.paper.page_count} 页</p><p className="sg-preview-abstract">{preview.paper.abstract ?? "这篇论文尚未提取摘要，可打开原文或补齐信息后查看。"}</p><div className="sg-form"><Link href={`/read/${preview.paper.id}`} className="sg-btn">打开阅读器</Link><Link href={`/papers/${preview.paper.id}`} className="sg-btn sg-btn--text">解析详情</Link></div><button className="sg-btn sg-btn--ghost sg-preview-return" onClick={() => { window.scrollTo({ top: previewScroll.current }); previewTrigger.current?.focus({ preventScroll: true }); }}>返回材料列表</button></div><p>这里显示论文元数据中的原文摘要，不是模型生成的总结。阅读位置与研究会话独立保留。</p></aside> : null}</div></> : null}
    <dialog ref={dialog} className="sg-edit-dialog" onCancel={() => { setEditing(null); setDeleting(null); }}>{editing ? <form onSubmit={async event => {
      event.preventDefault(); const fields = new FormData(event.currentTarget); setBusy(editing.paper.id);
      try { await workspacePost(`/papers/${editing.paper.id}`, { title: String(fields.get("title")).trim() || null, authors: String(fields.get("authors")).split("\n").map(s => s.trim()).filter(Boolean), institutions: String(fields.get("institutions")).split("\n").map(s => s.trim()).filter(Boolean), abstract: String(fields.get("abstract")).trim() || null, year: fields.get("year") ? Number(fields.get("year")) : null }, "PATCH"); setEditing(null); dialog.current?.close(); await load(); }
      catch (cause) { setError(cause instanceof Error ? cause.message : "信息未保存。"); } finally { setBusy(""); }
    }}><h2 className="sg-section__title">编辑论文信息</h2>{error ? <p role="alert" className="sg-error">{error}</p> : null}<p>修正会单独保存，原始解析记录保留。</p>{([['title', '标题', editing.paper.title ?? ''], ['authors', '作者（每行一人，按原文顺序）', editing.paper.authors.join('\n')], ['institutions', '机构（每行一项）', editing.paper.institutions.join('\n')], ['abstract', '摘要', editing.paper.abstract ?? '']] as const).map(([name, label, value]) => <label className="sg-field" key={`${editing.paper.id}-${name}`}>{label}<textarea className="sg-input" name={name} aria-label={label} defaultValue={value} rows={name === "abstract" ? 5 : 2} /></label>)}<label className="sg-field">年份<input className="sg-input" name="year" type="number" min="1" max="9999" defaultValue={editing.paper.year ?? ""} /></label><div className="sg-form"><button className="sg-btn" disabled={!!busy}>保存修正</button><button type="button" className="sg-btn sg-btn--ghost" onClick={() => { setEditing(null); dialog.current?.close(); }}>取消</button></div></form> : deleting ? <><h2 className="sg-section__title">移入回收站？</h2><p>{deleting.paper.title ?? deleting.paper.arxiv_id ?? "这篇论文"}</p><p>原件和历史不会删除，可随时从回收站恢复。</p><div className="sg-form"><button className="sg-btn" disabled={!!busy} onClick={() => void action(deleting, "delete")}>移入回收站</button><button className="sg-btn sg-btn--ghost" onClick={() => { setDeleting(null); dialog.current?.close(); }}>取消</button></div></> : null}</dialog>
  </main>;
}

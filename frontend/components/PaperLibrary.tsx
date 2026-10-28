"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import { getPaperViews, workspacePost, workspaceRequest, type PaperView } from "@/lib/workspace";
import type { Paged } from "@/lib/types";
import VersionResolution from "./VersionResolution";

export default function PaperLibrary() {
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
  return <main className="sg-shell"><div className="sg-page-head"><h1 className="sg-title">我的论文</h1><p className="sg-lede">从一篇论文开始阅读，把问题与证据留在同一个工作台。</p><div className="sg-form"><Link href="/upload" className="sg-btn">上传论文</Link><Link href="/qa" className="sg-btn sg-btn--ghost">跨篇研究</Link></div></div>
    <div className="sg-library-controls"><input className="sg-input" type="search" aria-label="搜索论文" placeholder="搜索标题或论文标识" value={query} onChange={event => { setQuery(event.target.value); setPage(1); }} /><button className="sg-btn sg-btn--ghost" aria-pressed={trash} onClick={() => { setTrash(!trash); setPage(1); }}>{trash ? "返回论文库" : "回收站"}</button><button className="sg-btn sg-btn--ghost" disabled={loading} onClick={load}>刷新</button></div>
    {error ? <div className="sg-error" role="alert"><p>{error}</p><Link href="/settings">检查服务状态</Link></div> : null}
    {notice ? <p role="status" className="sg-note">{notice}</p> : null}
    {loading ? <p role="status">正在读取论文信息…</p> : null}
    {data ? <><p className="sg-paper-card__meta">{trash ? "回收站" : "论文库"} · 共 {data.total} 篇</p><div className="sg-card-list">{data.items.map(view => <article className="sg-paper-card" key={view.paper.id}><div className="sg-paper-card__body"><h2 className="sg-paper-card__title"><Link href={`/read/${view.paper.id}`}>{view.paper.title || view.paper.arxiv_id || `信息待补齐的论文 · ${view.paper.page_count} 页`}</Link></h2><p className="sg-paper-card__meta">{view.paper.authors.join("、") || "作者信息待补齐"}</p><p className="sg-paper-card__meta">{view.paper.year ?? "年份待补齐"} · {view.paper.page_count} 页{view.paper.version ? ` · ${view.paper.version}` : ""} · {view.paper.has_text_layer ? "文本 PDF" : "扫描 PDF"}</p>{view.missing_fields.length ? <span className="sg-tag sg-tag--warning">基础信息待补齐</span> : <span className="sg-tag sg-tag--success">基础信息已提取</span>}<details className="sg-diag"><summary>来源信息</summary><p>{view.paper.source}</p>{view.year_source === "arxiv_submission_identifier" ? <p>年份依据原文 arXiv 编号的首次提交月份，代表预印本年份。</p> : null}<p className="sg-mono">{view.paper.id}</p><p>信息来源：{view.source === "user_correction" ? "人工修正" : view.source === "grobid_enrichment" ? "原文结构提取" : "初始解析"}</p></details></div><div className="sg-paper-card__actions">{trash ? <button className="sg-btn" disabled={busy === view.paper.id} onClick={() => void action(view, "restore")}>恢复论文</button> : <><Link href={`/read/${view.paper.id}`} className="sg-btn">阅读</Link><Link href={`/qa?paper=${view.paper.id}`} className="sg-btn sg-btn--ghost">提问</Link><button className="sg-btn sg-btn--ghost" onClick={() => setEditing(view)}>编辑信息</button>{(view.missing_fields.length || !view.author_profiles.length) ? <button className="sg-btn sg-btn--ghost" disabled={busy === view.paper.id} onClick={() => void action(view, "enrich")}>{busy === view.paper.id ? "原文提取中…" : "补齐信息"}</button> : null}<VersionResolution paperId={view.paper.id} onResolved={load} /><button className="sg-btn sg-btn--ghost" onClick={() => setDeleting(view)}>移入回收站</button></>}</div></article>)}</div>{!data.items.length && !loading ? <section className="sg-section"><h2 className="sg-section__title">{trash ? "回收站为空" : query ? "没有匹配的论文" : "还没有论文"}</h2><p>{trash ? "删除的论文会显示在这里，可以恢复。" : query ? "尝试其他标题或清空搜索条件。" : "上传 PDF 后，可阅读原文、提问并追踪引用。"}</p>{!trash && !query ? <Link href="/upload" className="sg-btn">上传第一篇论文</Link> : null}</section> : null}<div className="sg-pagination"><button className="sg-btn sg-btn--ghost" disabled={page <= 1 || loading} onClick={() => setPage(page - 1)}>上一页</button><span>第 {data.total_pages ? data.page : 0} / {data.total_pages} 页</span><button className="sg-btn sg-btn--ghost" disabled={!data.has_next || loading} onClick={() => setPage(page + 1)}>下一页</button></div></> : null}
    <dialog ref={dialog} className="sg-edit-dialog" onCancel={() => { setEditing(null); setDeleting(null); }}>{editing ? <form onSubmit={async event => {
      event.preventDefault(); const fields = new FormData(event.currentTarget); setBusy(editing.paper.id);
      try { await workspacePost(`/papers/${editing.paper.id}`, { title: String(fields.get("title")).trim() || null, authors: String(fields.get("authors")).split("\n").map(s => s.trim()).filter(Boolean), institutions: String(fields.get("institutions")).split("\n").map(s => s.trim()).filter(Boolean), abstract: String(fields.get("abstract")).trim() || null, year: fields.get("year") ? Number(fields.get("year")) : null }, "PATCH"); setEditing(null); dialog.current?.close(); await load(); }
      catch (cause) { setError(cause instanceof Error ? cause.message : "信息未保存。"); } finally { setBusy(""); }
    }}><h2 className="sg-section__title">编辑论文信息</h2>{error ? <p role="alert" className="sg-error">{error}</p> : null}<p>修正会单独保存，原始解析记录保留。</p>{([['title', '标题', editing.paper.title ?? ''], ['authors', '作者（每行一人，按原文顺序）', editing.paper.authors.join('\n')], ['institutions', '机构（每行一项）', editing.paper.institutions.join('\n')], ['abstract', '摘要', editing.paper.abstract ?? '']] as const).map(([name, label, value]) => <label className="sg-field" key={`${editing.paper.id}-${name}`}>{label}<textarea className="sg-input" name={name} aria-label={label} defaultValue={value} rows={name === "abstract" ? 5 : 2} /></label>)}<label className="sg-field">年份<input className="sg-input" name="year" type="number" min="1" max="9999" defaultValue={editing.paper.year ?? ""} /></label><div className="sg-form"><button className="sg-btn" disabled={!!busy}>保存修正</button><button type="button" className="sg-btn sg-btn--ghost" onClick={() => { setEditing(null); dialog.current?.close(); }}>取消</button></div></form> : deleting ? <><h2 className="sg-section__title">移入回收站？</h2><p>{deleting.paper.title ?? deleting.paper.arxiv_id ?? "这篇论文"}</p><p>原件和历史不会删除，可随时从回收站恢复。</p><div className="sg-form"><button className="sg-btn" disabled={!!busy} onClick={() => void action(deleting, "delete")}>移入回收站</button><button className="sg-btn sg-btn--ghost" onClick={() => { setDeleting(null); dialog.current?.close(); }}>取消</button></div></> : null}</dialog>
  </main>;
}

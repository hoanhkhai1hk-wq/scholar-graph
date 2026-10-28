"use client";
import { useRef, useState } from "react";
import { workspacePost, type PaperView } from "@/lib/workspace";
interface Mapping { name: string; institutions: string[]; emails: string[]; }
export default function AuthorProfileEditor({ metadata, onSaved }: { metadata: PaperView; onSaved: () => void }) {
  const dialog = useRef<HTMLDialogElement>(null);
  const [rows, setRows] = useState<Mapping[]>([]), [error, setError] = useState(""), [busy, setBusy] = useState(false);
  function open() {
    const prior = metadata.author_profiles as Mapping[];
    setRows(metadata.paper.authors.map(name => ({ name, institutions: prior.find(p => p.name === name)?.institutions ?? [], emails: prior.find(p => p.name === name)?.emails ?? [] })));
    setError(""); dialog.current?.showModal();
  }
  function change(index: number, field: "institutions" | "emails", value: string) {
    setRows(old => old.map((row, i) => i === index ? { ...row, [field]: value.split("；") } : row));
  }
  return <><button className="sg-btn sg-btn--ghost" disabled={!metadata.paper.authors.length} title={!metadata.paper.authors.length ? "请先在论文库补齐作者名单" : undefined} onClick={open}>补齐作者机构与邮箱</button><dialog ref={dialog} className="sg-edit-dialog"><form onSubmit={async event => {
    event.preventDefault(); setBusy(true); setError("");
    try { const fields = new FormData(event.currentTarget); await workspacePost(`/papers/${metadata.paper.id}/author-profiles`, { profiles: rows.map(row => ({ ...row, institutions: row.institutions.map(s => s.trim()).filter(Boolean), emails: row.emails.map(s => s.trim()).filter(Boolean) })), note: String(fields.get("note")) }, "PATCH"); dialog.current?.close(); onSaved(); }
    catch (cause) { setError(cause instanceof Error ? cause.message : "作者信息未保存。"); }
    finally { setBusy(false); }
  }}><h2 className="sg-section__title">补齐作者对应信息</h2><p>作者顺序沿用当前名单。机构、邮箱按原文填写，多项用中文分号分隔；人工补齐会单独标记并保留历史。</p>{error ? <p role="alert" className="sg-error">{error}</p> : null}{rows.map((row, index) => <fieldset key={row.name}><legend>{index + 1}. {row.name}</legend><label className="sg-field">对应机构<input className="sg-input" aria-label={`${row.name}的机构`} value={row.institutions.join("；")} onChange={event => change(index, "institutions", event.target.value)} /></label><label className="sg-field">邮箱<input className="sg-input" aria-label={`${row.name}的邮箱`} value={row.emails.join("；")} onChange={event => change(index, "emails", event.target.value)} /></label></fieldset>)}<label className="sg-field">核对说明<input className="sg-input" name="note" required maxLength={1000} placeholder="例如：按第1页作者脚注补齐" /></label><div className="sg-form"><button className="sg-btn" disabled={busy}>保存作者信息</button><button className="sg-btn sg-btn--ghost" type="button" onClick={() => dialog.current?.close()}>取消</button></div></form></dialog></>;
}

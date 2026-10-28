"use client";

import Link from "next/link";
import { useState } from "react";
import { workspacePost, workspaceRequest, type PaperView } from "@/lib/workspace";
import type { DedupDecision, DiffSummary } from "@/lib/types";
import AnchorTag from "./AnchorTag";

type Choice = "keep_old" | "keep_new" | "keep_both";
const LABELS: Record<string, string> = { keep_old: "保留已有", keep_new: "使用本次上传", keep_both: "保留两份", manual_review: "需要核对原文" };
interface VersionGroup { decision: DedupDecision; diff: DiffSummary; old: PaperView; new: PaperView;
  selection: { choice: Choice; at: string } | null; history: { choice: Choice; at: string }[]; }

export default function VersionResolution({ paperId, onResolved }: { paperId: string; onResolved?: () => void }) {
  const [groups, setGroups] = useState<VersionGroup[] | null>(null), [open, setOpen] = useState(false);
  const [status, setStatus] = useState(""), [busy, setBusy] = useState(false);
  async function load() { setGroups(await workspaceRequest<VersionGroup[]>(`/papers/${paperId}/versions`)); }
  async function inspect() {
    setOpen(!open); if (open) return; setBusy(true); setStatus("");
    try { await load(); } catch (cause) { setStatus(cause instanceof Error ? cause.message : "版本信息暂时不可用。"); }
    finally { setBusy(false); }
  }
  async function choose(newId: string, choice: Choice) {
    setBusy(true); setStatus("");
    try { await workspacePost(`/papers/${newId}/version-choice`, { choice }); await load(); setStatus("版本选择已保存，原件与历史记录均保留。"); onResolved?.(); }
    catch (cause) { setStatus(cause instanceof Error ? cause.message : "版本选择未保存。"); }
    finally { setBusy(false); }
  }
  return <div className="sg-version-manager"><button className="sg-btn sg-btn--ghost" onClick={inspect} disabled={busy} aria-expanded={open}>{busy ? "处理中…" : "版本管理"}</button>{open ? <div className="sg-note sg-version-pane"><p role="status">{status}</p>{groups?.length === 0 ? <p>这篇论文没有发现需要处理的相似版本。</p> : null}{groups?.map(group => <section key={group.new.paper.id}>
    <p>内容相似度：{(group.decision.similarity * 100).toFixed(1)}%。系统建议：{LABELS[group.decision.recommendation]}。</p>
    <p>{group.decision.evidence[0]?.reason}</p>
    <div className="sg-form">{([['已有版本', group.old], ['本次上传', group.new]] as const).map(([label, view]) => <p key={label}><strong>{label}：</strong><Link href={`/read/${view.paper.id}`}>{view.paper.title ?? "未命名论文"} {view.paper.version ?? ""}</Link> · {view.paper.page_count} 页 · {view.hidden_version ? "已隐藏，原件可读" : "论文库可见"}</p>)}</div>
    <p>检出 {group.diff.changed_sections.length} 处章节或分块变化。</p><details><summary>查看差异及原文证据</summary><p>不同版本的章节划分也会影响差异结果，可打开两个原件核对。</p><p>{group.diff.summary_text}</p><ul>{group.diff.changed_sections.map((section, i) => <li key={i}>{section}</li>)}</ul>{group.diff.key_sentences.map((item, i) => <div key={i}><blockquote>{item.text}</blockquote><AnchorTag anchor={item.anchor} /></div>)}</details>
    <p>当前选择：{group.selection ? LABELS[group.selection.choice] : "尚未选择"}。选择会改变论文库中显示的版本，原始文件与解析记录保留。</p>
    <div className="sg-form">{(["keep_old", "keep_new", "keep_both"] as Choice[]).map(choice => <button key={choice} className="sg-btn sg-btn--ghost" disabled={busy} onClick={() => void choose(group.new.paper.id, choice)}>{LABELS[choice]}</button>)}</div>
    <details><summary>选择历史（{group.history.length}）</summary>{group.history.length ? <ol>{group.history.map((item, i) => <li key={i}>{new Date(item.at).toLocaleString("zh-CN")} · {LABELS[item.choice]}</li>)}</ol> : <p>尚无人工选择记录。</p>}</details>
  </section>)}</div> : null}</div>;
}

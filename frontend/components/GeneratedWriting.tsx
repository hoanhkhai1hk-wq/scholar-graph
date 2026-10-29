"use client";

import { useCallback, useEffect, useState } from "react";
import type { Anchor, PaperMeta } from "@/lib/types";
import { workspacePost } from "@/lib/workspace";
import TaskMonitor, { type WorkspaceTask } from "./TaskMonitor";
import PaperPicker from "./PaperPicker";
import AnchorTag from "./AnchorTag";
import FutureDirections, { type Future } from "./FutureDirections";

interface Document { title: string; sections: { title: string; paragraphs: { text: string; type: string; citations: { quote: string; anchor: Anchor }[] }[] }[]; references: { paper_id: string; title: string | null; authors: string[]; year: number | null; source: string | null }[]; review_notice: string; }
interface Topology { nodes: { id: string; label: string; column: number; row: number; anchors: Anchor[] }[]; edges: { from_id: string; to_id: string; label: string; anchors: Anchor[] }[]; scripts: { format: string; script: string }[]; }
function download(text: string, name: string) { const url = URL.createObjectURL(new Blob([text], { type: "text/plain;charset=utf-8" })); const a = document.createElement("a"); a.href = url; a.download = name; a.click(); setTimeout(() => URL.revokeObjectURL(url), 1000); }

export default function GeneratedWriting({ papers }: { papers: PaperMeta[] }) {
  const [selected, setSelected] = useState<string[]>([]);
  const [idea, setIdea] = useState("");
  const [kind, setKind] = useState("outline");
  const [taskId, setTaskId] = useState("");
  const [document, setDocument] = useState<Document | null>(null);
  const [topology, setTopology] = useState<Topology | null>(null);
  const [future, setFuture] = useState<Future | null>(null);
  const [busy, setBusy] = useState(false);
  const [active, setActive] = useState(false);
  const [error, setError] = useState("");
  useEffect(() => { setTaskId(localStorage.getItem("sg.writing.task") ?? ""); setIdea(localStorage.getItem("sg.writing.idea") ?? ""); try { const saved = JSON.parse(localStorage.getItem("sg.writing.scope") ?? "[]"); if (Array.isArray(saved)) setSelected(saved.filter(id => papers.some(p => p.id === id)).slice(0,20)); } catch {} const savedKind = localStorage.getItem("sg.writing.kind"); if (savedKind && ["review","outline","topology","future"].includes(savedKind)) setKind(savedKind); const query = new URLSearchParams(location.search); const ids = (query.get("papers") ?? "").split(",").filter(id => papers.some(p => p.id === id)); if (ids.length && ids.length <= 20) { setSelected([...new Set(ids)]); setIdea("结合所选论文的实际引用关系，归纳研究主线、核心方法与局限，生成有原文依据的简短综述。"); } if (["review", "outline", "topology", "future"].includes(query.get("kind") ?? "")) setKind(query.get("kind")!); }, []);
  const receive = useCallback((value: NonNullable<WorkspaceTask["result"]>) => { setDocument(value.document as Document ?? null); setTopology(value.topology as Topology ?? null); setFuture(value.future as Future ?? null); }, []);
  function remember(id: string) { setTaskId(id); localStorage.setItem("sg.writing.task", id); }
  async function generate() {
    setBusy(true); setError(""); setDocument(null); setTopology(null); setFuture(null);
    try { const task = await workspacePost<WorkspaceTask>("/writing/tasks", { paper_ids: selected, idea, kind }); remember(task.id); setActive(true); }
    catch (cause) { setError(cause instanceof Error ? cause.message : "生成未能开始。"); }
    finally { setBusy(false); }
  }
  const positions = new Map(topology?.nodes.map((node, index) => [node.id, { x: 130 + node.column * 280, y: 55 + (node.row ?? index) * 115 }]) ?? []);
  return <section className="sg-section"><h2 className="sg-section__title">研究想法与文献写作</h2><p>选择论文并输入研究想法，生成带原文依据的论文框架、连贯综述或方法拓扑。生成内容会发送给已配置的 DeepSeek。</p>
    <PaperPicker papers={papers} selected={selected} onChange={ids => { setSelected(ids); localStorage.setItem("sg.writing.scope", JSON.stringify(ids)); }} disabled={busy || active} maxSelections={20} multiple label="参考论文（最多 20 篇）" />
    <label className="sg-field">研究想法或写作要求<textarea className="sg-input sg-input--area" disabled={busy || active} aria-label="研究想法或写作要求" value={idea} placeholder="例如：比较注意力架构与双向预训练，设计低资源场景的研究方案" onChange={event => { setIdea(event.target.value); localStorage.setItem("sg.writing.idea", event.target.value); }} /></label>
    <div className="sg-form"><label className="sg-field">生成内容<select className="sg-input" disabled={busy || active} value={kind} onChange={event => { setKind(event.target.value); localStorage.setItem("sg.writing.kind", event.target.value); }}><option value="outline">论文框架（摘要、引言、相关工作等）</option><option value="review">文献综述</option><option value="topology">论文方法拓扑与绘图代码</option><option value="future">未来工作与更新研究对照</option></select></label><button className="sg-btn" disabled={busy || active || selected.length < 1 || selected.length > 20 || idea.trim().length < 5} title={active ? "当前任务处理中，可在任务区停止或等待完成" : selected.length > 20 ? "单次最多选择二十篇论文" : !selected.length ? "先选择参考论文" : idea.trim().length < 5 ? "请输入至少 5 个字的研究想法" : undefined} onClick={() => void generate()}>{busy ? "正在创建任务…" : "开始生成"}</button></div>
    {error ? <p className="sg-error" role="alert">{error}</p> : null}{taskId ? <TaskMonitor taskId={taskId} onTaskChange={remember} onResult={receive} onStatus={status => setActive(["queued", "running", "cancelling"].includes(status))} /> : null}
    {document || topology || future ? <p>下方显示最近一次任务结果；新的选择在重新生成后生效。</p> : null}{document ? <article><h2>{document.title}</h2><p className="sg-note">{document.review_notice}</p>{document.sections.map((section, index) => <section key={index}><h3>{section.title}</h3>{section.paragraphs.map((p, i) => <div key={i} className="sg-writing-paragraph"><span className="sg-tag">{p.type === "proposal" ? "研究设想 · 尚未验证" : "文献归纳"}</span><p className="sg-prose">{p.text}</p>{p.citations.map((citation, n) => <details key={n}><summary>查看原文依据 {n + 1}</summary><blockquote>{citation.quote}</blockquote><AnchorTag anchor={citation.anchor} /></details>)}</div>)}</section>)}<h3>参考文献</h3><ol>{document.references.map(ref => <li key={ref.paper_id}>{ref.authors.join(", ")} · {ref.year ?? "年份待核对"} · {ref.title ?? "标题未提取"} <a href={`/read/${ref.paper_id}`}>阅读原文</a></li>)}</ol><button className="sg-btn sg-btn--ghost" onClick={() => download(JSON.stringify(document, null, 2), "文献写作与来源.json")}>导出内容与来源</button></article> : null}
    {future ? <FutureDirections value={future} /> : null}
    {topology ? <><h3>方法逻辑拓扑</h3><p>节点与关系由模型从原文中提取，需结合下方原文依据复核。</p><div className="sg-topology-scroll"><svg role="img" aria-label="论文方法拓扑" viewBox={`0 0 ${Math.max(600, ...[...positions.values()].map(p => p.x + 150))} ${Math.max(250, ...[...positions.values()].map(p => p.y + 70))}`}><defs><marker id="logic-arrow" markerWidth="8" markerHeight="8" refX="7" refY="3" orient="auto"><path d="M0,0 L0,6 L8,3 z" fill="#14544b" /></marker></defs>{topology.edges.map((edge, i) => { const from = positions.get(edge.from_id), to = positions.get(edge.to_id); return from && to ? <g key={i}><line x1={from.x} y1={from.y + 22} x2={to.x} y2={to.y - 22} stroke="#718b7e" markerEnd="url(#logic-arrow)" /><text x={(from.x + to.x) / 2} y={(from.y + to.y) / 2 - 10} textAnchor="middle" fontSize="12">{edge.label}</text></g> : null; })}{topology.nodes.map(node => { const p = positions.get(node.id)!; return <g key={node.id}><rect x={p.x - 110} y={p.y - 22} width="220" height="44" rx="8" fill="#e4eeea" stroke="#a5c9b7" /><text x={p.x} y={p.y + 5} textAnchor="middle" fontSize="14">{node.label}</text></g>; })}</svg></div>{topology.nodes.map(node => <details key={node.id}><summary>{node.label} · 原文依据</summary>{node.anchors.map((anchor, i) => <AnchorTag key={i} anchor={anchor} />)}</details>)}{topology.edges.map((edge, index) => <details key={`edge-${index}`}><summary>关系：{edge.label} · 原文依据</summary>{edge.anchors.map((anchor, i) => <AnchorTag key={i} anchor={anchor} />)}</details>)}{topology.scripts.map(script => <details key={script.format}><summary>{({ mermaid: "Mermaid 绘图代码", dot: "Graphviz 绘图代码", tikz: "LaTeX TikZ 绘图代码", matplotlib: "Matplotlib 绘图代码" } as Record<string, string>)[script.format]}</summary><pre className="sg-code">{script.script}</pre><button className="sg-btn sg-btn--ghost" onClick={() => download(script.script, `论文拓扑.${{ mermaid: "mmd", dot: "dot", tikz: "tex", matplotlib: "py" }[script.format]}`)}>下载代码</button></details>)}</> : null}
  </section>;
}

"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import type { Anchor, PaperMeta, ReferenceEntry } from "@/lib/types";
import { workspacePost, workspaceRequest } from "@/lib/workspace";
import TaskMonitor, { type WorkspaceTask } from "./TaskMonitor";
import AnchorTag from "./AnchorTag";
import DiscoveryStatus from "./DiscoveryStatus";

interface Plan { reference: ReferenceEntry; importance: number; basis: string; acquisition_ready: boolean; content_score: number; content_reasons: string[]; content_contexts: { quote: string; anchor: Anchor; marker_verified: boolean }[]; }
export default function AcquisitionPanel({ papers }: { papers: PaperMeta[] }) {
  const router = useRouter();
  const [title, setTitle] = useState(""), [seed, setSeed] = useState(""), [plan, setPlan] = useState<Plan[]>([]), [selected, setSelected] = useState<number[]>([]);
  const [task, setTask] = useState(""), [error, setError] = useState(""), [busy, setBusy] = useState(false), [frequency, setFrequency] = useState("daily"), [enabled, setEnabled] = useState(false), [notice, setNotice] = useState("");
  const [planBusy, setPlanBusy] = useState(false), [revision, setRevision] = useState(0);
  useEffect(() => { setTask(localStorage.getItem("sg.acquisition.task") ?? ""); void workspaceRequest<{ enabled: boolean; frequency: string; paper_ids: string[] }>("/tracking/schedule").then(config => { setEnabled(config.enabled); setFrequency(config.frequency); if (config.paper_ids.length) setSeed(config.paper_ids[0]); }).catch(cause => setError(cause.message)); }, []);
  useEffect(() => {
    let disposed = false; setSelected([]); setPlan([]); setError("");
    if (seed) { setPlanBusy(true); void workspaceRequest<Plan[]>(`/papers/${seed}/reference-plan`).then(value => { if (!disposed) setPlan(value); }).catch(cause => { if (!disposed) setError(cause.message); }).finally(() => { if (!disposed) setPlanBusy(false); }); }
    return () => { disposed = true; };
  }, [seed]);
  function remember(id: string) { setTask(id); localStorage.setItem("sg.acquisition.task", id); }
  async function acquire(numbers?: number[]) {
    setBusy(true); setError("");
    try { const next = await workspacePost<WorkspaceTask>(numbers ? `/papers/${seed}/reference-tasks` : "/acquisition/tasks", numbers ? { reference_numbers: numbers } : { title }); remember(next.id); }
    catch (cause) { setError(cause instanceof Error ? cause.message : "获取任务未能开始。"); }
    finally { setBusy(false); }
  }
  async function discover() { setBusy(true); setError(""); try { const next = await workspacePost<WorkspaceTask>("/tracking/tasks", { paper_ids: [seed], max_candidates: 3, max_imports: 1, force: true }); remember(next.id); } catch (cause) { setError(cause instanceof Error ? cause.message : "发现任务未能开始。"); } finally { setBusy(false); } }
  async function schedule() { setBusy(true); setError(""); setNotice(""); try { await workspacePost("/tracking/schedule", { enabled, frequency, paper_ids: [seed], max_imports: 1 }); setNotice(enabled ? "追踪计划已保存。后端保持运行时将按计划查找，逐项记录新增、重复与失败。" : "自动追踪已关闭。"); setRevision(v=>v+1); } catch (cause) { setError(cause instanceof Error ? cause.message : "计划未保存。"); } finally { setBusy(false); } }
  return <section className="sg-section sg-discovery"><h2 className="sg-section__title">自动获取与追踪计划</h2><p>按完整标题精确查找公开全文，或批量获取参考文献。无法取得全文时逐项说明原因。</p>
    <div className="sg-form"><label className="sg-field">论文完整标题<input className="sg-input" value={title} onChange={event => setTitle(event.target.value)} placeholder="输入论文标题" /></label><button className="sg-btn" disabled={busy || title.trim().length < 3} title={title.trim().length < 3 ? "请输入至少三个字符的完整论文标题" : undefined} onClick={() => void acquire()}>查找、下载并入库</button></div>
    {error ? <p className="sg-error" role="alert">{error}</p> : null}{notice ? <p role="status">{notice}</p> : null}
    {task ? <TaskMonitor taskId={task} onTaskChange={remember} onResult={() => { router.refresh(); setRevision(v=>v+1); }} /> : null}
    <label className="sg-field">参考论文与追踪主题<select className="sg-input" value={seed} onChange={event => setSeed(event.target.value)}><option value="">选择论文</option>{papers.map(p => <option key={p.id} value={p.id}>{p.title ?? p.arxiv_id ?? "未命名论文"}</option>)}</select></label>
    {seed ? <><h3>批量获取参考文献</h3><p>按引用所在章节、采用语句与主题词排序，点击依据可回到原文。筛选结果供研究时取舍，不自动删除文献，也不判断作者的引用动机。</p>
      <div className="sg-form"><button className="sg-btn" disabled={busy || !plan.length} onClick={() => void acquire(plan.slice(0,100).map(p=>p.reference.number))}>一键获取全部 {Math.min(plan.length,100)} 篇参考文献</button><button className="sg-btn sg-btn--ghost" disabled={!plan.length} onClick={() => setSelected(plan.filter(p=>p.content_contexts.length).slice(0,10).map(p=>p.reference.number))}>按内容选择前十项</button><button className="sg-btn sg-btn--ghost" disabled={!plan.length} onClick={() => setSelected([...plan].sort((a,b)=>b.importance-a.importance || a.reference.number-b.reference.number).slice(0,10).map(p=>p.reference.number))}>按引用次数选择前十项</button><button className="sg-btn sg-btn--ghost" onClick={() => setSelected([])}>清空选择</button></div>
      {plan.length>100 ? <p>单次上限一百项，本次获取前一百项；其余文献请分批选择。</p> : null}
      <div className="sg-reference-picker">{plan.map(item => <article key={item.reference.ref_id} className="sg-note"><label className="sg-chat__paper"><input type="checkbox" checked={selected.includes(item.reference.number)} disabled={!selected.includes(item.reference.number) && selected.length >= 100} onChange={() => setSelected(ids => ids.includes(item.reference.number) ? ids.filter(n => n !== item.reference.number) : [...ids, item.reference.number])} /><span><strong>[{item.reference.number}] {item.reference.title ?? item.reference.arxiv_id ?? "标题未提取"}</strong><span className="sg-paper-card__meta"> · {item.basis}</span>{!item.acquisition_ready ? <span> · 缺少检索标识，获取任务会报告原因</span> : null}</span></label><details><summary>内容筛选依据 · {item.content_score.toFixed(2)} 分</summary>{item.content_reasons.map((reason,i)=><p key={i}>{reason}</p>)}{item.content_contexts.slice(0,3).map((context,i)=><div key={i}><blockquote>{context.quote}</blockquote><AnchorTag anchor={context.anchor}/>{!context.marker_verified ? <p>引用标记未完整识别，请核对原文。</p> : null}</div>)}</details></article>)}{!plan.length ? <p>{planBusy ? "正在读取参考文献与原文依据…" : "没有解析出的参考文献，可先在论文库补齐信息。"}</p> : null}</div>
      <button className="sg-btn" disabled={busy || !selected.length} title={!selected.length ? "请先选择参考文献" : undefined} onClick={() => void acquire(selected)}>获取选中的 {selected.length} 篇文献</button>
      <h3>定时发现与推荐</h3><button className="sg-btn sg-btn--ghost" disabled={busy} onClick={() => void discover()}>立即发现新论文</button><div className="sg-form"><label className="sg-checkbox"><input type="checkbox" checked={enabled} onChange={event => setEnabled(event.target.checked)} />启用自动发现</label><label className="sg-field">执行频率<select className="sg-input" value={frequency} onChange={event => setFrequency(event.target.value)}><option value="daily">每日</option><option value="weekly">每周</option></select></label><button className="sg-btn" disabled={busy} onClick={() => void schedule()}>保存计划</button></div><p>每次最多尝试下载一篇新论文，库内重复不占下载名额；推荐列表使用最新论文库计算。</p></> : null}
    <DiscoveryStatus revision={revision}/>
  </section>;
}

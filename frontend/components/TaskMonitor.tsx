"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { workspacePost, workspaceRequest } from "@/lib/workspace";
import VersionResolution from "./VersionResolution";
import AsyncStatus from "./AsyncStatus";

export interface WorkspaceTask {
  id: string; kind: string; status: string; created_at: string; started_at: string | null; finished_at: string | null;
  progress: { completed_units: number; total_units: number | null; label: string };
  result: { succeeded?: { paper_id: string; filename: string; warning?: string; already_present?: boolean }[]; failed?: { filename: string; message: string; error_code: string; details?: { reason?: unknown } | null }[]; [key: string]: unknown } | null;
  error: { message: string; error_code: string } | null;
}
const labels: Record<string, string> = { queued: "排队中", running: "处理中", cancelling: "正在停止", completed: "已完成", partial: "部分成功", failed: "未完成", cancelled: "已停止", interrupted: "服务重启后待恢复" };
interface TrackingResult { candidate_count?: number; imported_count?: number; duplicate_count?: number; failed_count?: number; query_failed_count?: number; reason?: string; errors?: { message: string }[]; }
const active = new Set(["queued", "running", "cancelling"]);

export default function TaskMonitor({ taskId, onTaskChange, onResult, onStatus }: { taskId: string; onTaskChange?: (id: string) => void; onResult?: (result: NonNullable<WorkspaceTask["result"]>) => void; onStatus?: (status: string) => void }) {
  const [task, setTask] = useState<WorkspaceTask | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    const controller = new AbortController(); let timer: ReturnType<typeof setTimeout>;
    async function poll() {
      try {
        const next = await workspaceRequest<WorkspaceTask>(`/tasks/${taskId}`, { signal: controller.signal });
        if (controller.signal.aborted) return;
        setTask(next); setError(""); onStatus?.(next.status);
        if (active.has(next.status)) timer = setTimeout(poll, 2000);
        else if (next.result) onResult?.(next.result);
      } catch (cause) { if (!controller.signal.aborted) { setError(cause instanceof Error ? cause.message : "状态读取失败。"); timer = setTimeout(poll, 5000); } }
    }
    setTask(null); void poll();
    return () => { controller.abort(); clearTimeout(timer); };
  }, [taskId]);
  async function action(kind: "cancel" | "retry") {
    setBusy(true);
    try { const next = await workspacePost<WorkspaceTask>(`/tasks/${taskId}/${kind}`, {}); if (kind === "retry") onTaskChange?.(next.id); else setTask(next); }
    catch (cause) { setError(cause instanceof Error ? cause.message : "操作未完成。"); }
    finally { setBusy(false); }
  }
  const failures = task?.result?.failed ?? [];
  const tracking = task?.result?.tracking as TrackingResult | undefined;
  return <section className="sg-section" aria-live="polite"><div className="sg-section__head"><h2 className="sg-section__title">任务进度</h2><span className="sg-tag">{task ? labels[task.status] ?? task.status : "读取中…"}</span></div>{error ? <p className="sg-error" role="alert">{error} 状态读取会自动重试。</p> : null}{!task && !error ? <AsyncStatus label="正在读取任务进度…" rows={2} /> : null}{task ? <><p>{task.progress.label}</p>{task.progress.total_units !== null ? <p>已处理 {task.progress.completed_units} / {task.progress.total_units} 项</p> : null}<p className="sg-mono">开始：{new Date(task.created_at).toLocaleString("zh-CN")}{task.finished_at ? ` · 结束：${new Date(task.finished_at).toLocaleString("zh-CN")}` : ""}</p>{task.error ? <p role="alert">{task.error.message}</p> : null}{failures.length ? <div className="sg-error" role="alert"><strong>有 {failures.length} 项处理未完成</strong>{failures.slice(0,3).map((item,index) => <div key={index}><p>{item.filename}：{item.message}</p>{typeof item.details?.reason === "string" ? <p>失败原因：{item.details.reason}</p> : null}</div>)}<p>输入与已校验结果保留，可重试任务；完整原因可展开逐项结果查看。</p></div> : null}<div className="sg-form">{active.has(task.status) ? <button className="sg-btn sg-btn--ghost" disabled={busy || task.status === "cancelling"} onClick={() => void action("cancel")}>{task.status === "cancelling" ? "等待当前步骤停止…" : "请求停止"}</button> : ["partial", "failed", "cancelled", "interrupted"].includes(task.status) ? <button className="sg-btn" disabled={busy} onClick={() => void action("retry")}>重试任务</button> : null}</div>{tracking ? <div className="sg-note"><p>真实候选 {tracking.candidate_count ?? 0} 篇 · 新增 {tracking.imported_count ?? 0} 篇 · 重复 {tracking.duplicate_count ?? 0} 篇 · 下载或解析失败 {tracking.failed_count ?? 0} 篇 · 查询失败 {tracking.query_failed_count ?? 0} 条</p>{tracking.errors?.map((item, i) => <p key={i}>{item.message}</p>)}{tracking.reason ? <details><summary>运行原因</summary><p>{tracking.reason}</p></details> : null}</div> : null}{task.result?.succeeded || task.result?.failed ? <details><summary>逐项结果：{task.kind === "translation" ? `已校验 ${typeof task.result.succeeded_count === "number" ? task.result.succeeded_count : 0} 段，失败 ${task.result.failed?.length ?? 0} 批材料` : `成功或已存在 ${task.result.succeeded?.length ?? 0} 篇，失败 ${task.result.failed?.length ?? 0} 项`}（展开查看）</summary>{task.result?.succeeded?.map(item => <div className="sg-note" key={item.paper_id}><strong>{item.filename}</strong>{item.already_present ? <p>库中已有，已跳过下载。</p> : null}<p><Link href={`/read/${item.paper_id}`}>打开论文</Link></p>{item.warning ? <><p>{item.warning}</p><VersionResolution paperId={item.paper_id} /></> : null}</div>)}{task.result?.failed?.map((item, index) => <div className="sg-error" key={index}><strong>{item.filename}</strong><p>{item.message}</p></div>)}</details> : null}</> : null}</section>;
}

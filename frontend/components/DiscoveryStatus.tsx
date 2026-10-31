"use client";
import { useEffect, useState } from "react";
import { workspaceRequest } from "@/lib/workspace";
import EmptyState from "./EmptyState";
import AsyncStatus from "./AsyncStatus";
import { trackingErrorGroups } from "@/lib/tracking";
interface Run { status: string; duration_seconds: number | null; candidate_count: number; imported_count: number; duplicate_count: number; failed_count: number; query_failed_count?: number; query_succeeded_count?: number; discovered_count?: number; queries: { returned_count: number; error: { message: string } | null }[]; errors: { message: string }[]; finished_at: string | null; }
interface Status { latest_run: Run | null; scheduler_details: { enabled: boolean; active: boolean; interval_seconds: number; run_count: number } }
const labels: Record<string,string> = {running:"正在追踪",completed:"本次追踪已完成",partial:"本次追踪部分完成",failed:"本次追踪失败",interrupted:"本次追踪已中断"};
export default function DiscoveryStatus({revision}:{revision:number}) {
  const [status,setStatus]=useState<Status|null>(null),[error,setError]=useState("");
  useEffect(()=>{const controller=new AbortController();let timer:ReturnType<typeof setTimeout>;async function load(){try{const v=await workspaceRequest<Status>("/tracking/status",{signal:controller.signal});if(!controller.signal.aborted){setStatus(v);setError("");}}catch(cause){if(!controller.signal.aborted)setError(cause instanceof Error?cause.message:"追踪状态暂时无法读取。");}finally{if(!controller.signal.aborted)timer=setTimeout(load,10000);}}void load();return()=>{controller.abort();clearTimeout(timer);};},[revision]);
  const run=status?.latest_run,scheduler=status?.scheduler_details;
  const noNew = run?.status === "completed" && run.imported_count === 0 && run.failed_count === 0 && !run.query_failed_count && run.errors.length === 0;
  const groups = trackingErrorGroups(run?.errors ?? []);
  const failures = run?.query_failed_count ?? run?.queries.filter(q=>q.error).length ?? 0;
  const succeeded = run?.query_succeeded_count ?? (run ? run.queries.length - failures : 0);
  return <section className="sg-note" aria-live="polite" aria-label="最近追踪记录"><h3>最近追踪记录</h3>
    {scheduler ? <p>自动发现{scheduler.enabled ? "已启用" : "已关闭"} · {scheduler.active ? "调度器运行中" : "调度器未运行"} · 已自动执行 {scheduler.run_count} 次</p> : null}
    {error ? <p className="sg-error" role="alert">{error} 状态读取会自动重试。</p> : null}
    {run ? <>
      <p><strong>{labels[run.status]??"状态待核对"}</strong>{run.finished_at ? ` · ${new Date(run.finished_at).toLocaleString("zh-CN")}` : ""}</p>
      <p>已执行查询 {run.queries.length} 条：成功 {succeeded} 条，失败 {failures} 条。</p>
      <p>发现候选 {run.discovered_count ?? run.candidate_count} 篇 · 已入库 {run.imported_count} 篇 · 重复 {run.duplicate_count} 篇 · 下载或解析失败 {run.failed_count} 篇</p>
      {groups.length ? <div role="alert" className="sg-error"><p>{run.status === "running" ? "部分请求尚未完成，任务仍在继续。" : "本次结果不完整；已有候选会保留，未完成的查询可稍后重试。"}</p>
        {groups.map(({message,count})=><p key={message}>{message}{count>1?`（共 ${count} 条）`:""}</p>)}</div> : null}
      {run.candidate_count>0 && run.errors.length>0 ? <p>候选表示已发现的文献线索，不等于已下载或已入库的论文。</p> : null}
      {run.errors.length ? <details><summary>逐条查询与错误诊断（{run.errors.length} 条）</summary><pre className="sg-synthesis">{JSON.stringify({queries:run.queries,errors:run.errors},null,2)}</pre></details> : null}
      {run.duration_seconds!==null ? <p>本次耗时 {run.duration_seconds} 秒。</p> : null}
    </> : status ? <EmptyState variant="tracking" title="还没有追踪记录" hint="选择主题论文后，可立即发现或启用每日／每周计划。" action={<a href="#tracking-theme">选择追踪主题</a>} /> : !error ? <AsyncStatus label="正在读取追踪记录…" rows={2} /> : null}
    {noNew ? <EmptyState variant="tracking" title="本次没有新增论文" hint="当前查询已完成；可以查看候选与重复记录，或调整主题等待下次发现。" action={<a href="#tracking-theme">调整追踪主题</a>} /> : null}
  </section>;
}

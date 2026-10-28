"use client";
import { useEffect, useState } from "react";
import { workspaceRequest } from "@/lib/workspace";
interface Run { status: string; duration_seconds: number | null; candidate_count: number; imported_count: number; duplicate_count: number; failed_count: number; query_failed_count?: number; queries: { returned_count: number; error: { message: string } | null }[]; errors: { message: string }[]; finished_at: string | null; }
interface Status { latest_run: Run | null; scheduler_details: { enabled: boolean; active: boolean; interval_seconds: number; run_count: number } }
const labels: Record<string,string> = {running:"正在追踪",completed:"本次追踪已完成",partial:"本次追踪部分成功",failed:"本次追踪失败",interrupted:"本次追踪已中断"};
export default function DiscoveryStatus({revision}:{revision:number}) {
  const [status,setStatus]=useState<Status|null>(null),[error,setError]=useState("");
  useEffect(()=>{const controller=new AbortController();let timer:ReturnType<typeof setTimeout>;async function load(){try{const v=await workspaceRequest<Status>("/tracking/status",{signal:controller.signal});if(!controller.signal.aborted){setStatus(v);setError("");}}catch(cause){if(!controller.signal.aborted)setError(cause instanceof Error?cause.message:"追踪状态暂时无法读取。");}finally{if(!controller.signal.aborted)timer=setTimeout(load,10000);}}void load();return()=>{controller.abort();clearTimeout(timer);};},[revision]);
  const run=status?.latest_run,scheduler=status?.scheduler_details;
  return <section className="sg-note" aria-live="polite"><h3>最近追踪记录</h3>{scheduler ? <p>自动发现{scheduler.enabled ? "已启用" : "已关闭"} · {scheduler.active ? "调度器运行中" : "调度器未运行"} · 已自动执行 {scheduler.run_count} 次</p> : null}{error ? <p className="sg-error" role="alert">{error} 状态读取会自动重试。</p> : null}{run ? <><p><strong>{labels[run.status]??"状态待核对"}</strong>{run.finished_at ? ` · ${new Date(run.finished_at).toLocaleString("zh-CN")}` : ""}</p><p>执行查询 {run.queries.length} 条 · 查询失败 {run.query_failed_count??run.queries.filter(q=>q.error).length} 条 · 候选 {run.candidate_count} 篇 · 新增 {run.imported_count} 篇 · 重复 {run.duplicate_count} 篇 · 下载或解析失败 {run.failed_count} 篇</p>{run.errors.map((e,i)=><p role="alert" className="sg-error" key={i}>{e.message}</p>)}{run.duration_seconds!==null ? <p>本次耗时 {run.duration_seconds} 秒。</p> : null}</> : <p>尚未运行。选择主题论文后，可立即发现或启用每日／每周计划。</p>}</section>;
}

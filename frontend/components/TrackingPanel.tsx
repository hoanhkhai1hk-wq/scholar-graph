"use client";

import { useCallback, useEffect, useState } from "react";
import { fetchTrackingStatus, runTracking } from "@/lib/api";
import type { TrackingStatus } from "@/lib/types";
import ErrorState from "./ErrorState";
import EmptyState from "./EmptyState";
import AsyncStatus from "./AsyncStatus";
import { trackingErrorGroups } from "@/lib/tracking";

const LABELS: Record<string, string> = {
  running: "正在追踪", completed: "追踪已完成", partial: "部分完成",
  failed: "追踪失败", interrupted: "追踪已中断",
};
function statusTag(value: string) {
  const tone = value === "completed" ? "success" : value === "running" ? "muted" :
    value === "partial" || value === "interrupted" ? "warning" : "error";
  return <span className={`sg-tag sg-tag--${tone}`}>{LABELS[value] ?? "状态待核对"}</span>;
}
function timestamp(value: string | null) {
  return value ? new Date(value).toLocaleString("zh-CN") : "尚未结束";
}

export default function TrackingPanel({ paperIds }: { paperIds: string[] }) {
  const [status, setStatus] = useState<TrackingStatus | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [submitting, setSubmitting] = useState(false);
  const [now, setNow] = useState(Date.now());
  const load = useCallback(async () => {
    try { setStatus(await fetchTrackingStatus()); setError(null); }
    catch (cause) { setError(cause); }
    setNow(Date.now());
  }, []);
  useEffect(() => {
    let disposed = false;
    let timer: ReturnType<typeof setTimeout>;
    async function poll() {
      if (!document.hidden) await load();
      if (!disposed) timer = setTimeout(poll, 5000);
    }
    void poll();
    return () => { disposed = true; clearTimeout(timer); };
  }, [load]);

  async function trigger() {
    setSubmitting(true); setError(null);
    try {
      // This preserved compatibility action discovers candidates only. The main
      // acquisition panel offers an asynchronous task that can also import them.
      await runTracking({ paper_ids: paperIds.slice(0, 5), max_candidates: 3, max_imports: 0, force: true });
      await load();
    } catch (cause) { setError(cause); }
    finally { setSubmitting(false); }
  }

  const run = status?.latest_run ?? null, scheduler = status?.scheduler_details;
  const inProgress = run?.status === "running";
  const queryFailures = run?.query_failed_count ?? run?.queries.filter(q => q.error).length ?? 0;
  const groups = trackingErrorGroups(run?.errors ?? []);
  const noNew = run?.status === "completed" && run.imported_count === 0 && run.failed_count === 0 &&
    queryFailures === 0 && run.errors.length === 0;
  const elapsed = run?.duration_seconds ?? (run?.started_at ? Math.max(0, Math.floor((now - Date.parse(run.started_at)) / 1000)) : null);
  const phase = run?.phase === "importing" ? "正在下载与解析候选论文" : "正在查询公开论文，结果尚未最终确认";

  return <section aria-label="arXiv追踪运行状态">
    <div className="sg-form">
      <button className="sg-btn" disabled={submitting || inProgress || !paperIds.length}
        title={!paperIds.length ? "请先上传论文" : inProgress ? "已有追踪任务正在运行，请等待本次结束" : undefined}
        onClick={() => void trigger()}>{submitting || inProgress ? "正在追踪…" : "立即运行一次追踪"}</button>
      <button className="sg-btn sg-btn--ghost" onClick={() => void load()}>刷新状态</button>
    </div>
    <p>此处手动操作只发现候选，不下载入库；需要获取全文时使用上方“自动获取与追踪计划”。状态每五秒自动刷新。</p>
    {scheduler ? <p>自动调度{scheduler.enabled ? "已启用" : "已关闭"} · {scheduler.active ? "调度器运行中" : "调度器未运行"} · 已自动执行 {scheduler.run_count ?? 0} 次</p> : null}
    {run ? <>
      <p>最近一次运行：{statusTag(run.status)}{elapsed !== null ? ` · 已用时 ${elapsed} 秒` : ""}</p>
      {inProgress ? <p role="status">{phase}；查询失败会单独计数，不代表全部查询均失败。</p> : null}
      <dl className="sg-kv">
        <dt>执行查询</dt><dd>{run.queries.length}{run.query_total_count ? ` / ${run.query_total_count}` : ""} 条</dd>
        <dt>查询失败</dt><dd>{queryFailures} 条</dd>
        <dt>发现候选</dt><dd>{run.discovered_count ?? run.candidate_count} 篇</dd>
        <dt>新增与重复</dt><dd>新增 {run.imported_count} 篇 · 重复 {run.duplicate_count} 篇</dd>
        <dt>下载或解析失败</dt><dd>{run.failed_count} 篇</dd>
        <dt>开始时间</dt><dd>{timestamp(run.started_at)}</dd>
        <dt>结束时间</dt><dd>{timestamp(run.finished_at)}</dd>
      </dl>
      {groups.length ? <div className="sg-error" role="alert">
        <p>本次有查询或获取未完成。已完成的结果会保留，失败项可稍后重试。</p>
        {groups.map(({message, count}) => <p key={message}>{message}{count > 1 ? `（共 ${count} 条）` : ""}</p>)}
      </div> : null}
      <details><summary>诊断信息与逐条原始结果</summary><pre className="sg-synthesis">{JSON.stringify({
        run_id: run.run_id, status: run.status, phase: run.phase,
        scheduler, queries: run.queries, errors: run.errors,
        dedup_record_count: status?.dedup_records.length,
      }, null, 2)}</pre></details>
      {noNew ? <EmptyState variant="tracking" title="本次没有新增论文"
        hint={run.max_imports === 0 ? "本次查询已完成，仅发现候选，未要求下载入库。需要全文时可使用上方获取入口。" : "本次查询已完成；可以查看候选与重复记录，或调整追踪主题。"} /> : null}
    </> : !status && !error ? <AsyncStatus label="正在读取追踪记录…" rows={2} /> : null}
    {status && !run ? <EmptyState variant="tracking" title="还没有运行记录" hint="先运行一次追踪，或在上方选择主题并保存自动发现计划。" /> : null}
    {error ? <ErrorState title="追踪请求或状态读取失败" error={error} /> : null}
  </section>;
}

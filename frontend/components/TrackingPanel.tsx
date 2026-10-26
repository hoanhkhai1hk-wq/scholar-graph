"use client";

import { useCallback, useEffect, useState } from "react";
import { fetchTrackingStatus, runTracking } from "@/lib/api";
import type { TrackingRun, TrackingStatus } from "@/lib/types";
import ErrorState from "./ErrorState";

function statusTag(status: string | null) {
  if (!status) return <span className="sg-tag sg-tag--muted">尚未运行</span>;
  if (status === "completed")
    return <span className="sg-tag sg-tag--success">completed</span>;
  if (status === "partial")
    return <span className="sg-tag sg-tag--warning">partial（部分成功）</span>;
  return <span className="sg-tag sg-tag--error">{status}</span>;
}

/**
 * 追踪运行状态面板：把「最近一次运行、新增数、失败原因」摆在页面上。
 * 失败原因原样展示后端三字段错误，不改写、不省略。
 */
export default function TrackingPanel({ paperIds }: { paperIds: string[] }) {
  const [status, setStatus] = useState<TrackingStatus | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [running, setRunning] = useState(false);
  const [lastRun, setLastRun] = useState<TrackingRun | null>(null);

  const load = useCallback(async () => {
    try {
      const value = await fetchTrackingStatus();
      setStatus(value);
      setError(null);
    } catch (cause) {
      setError(cause);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  async function trigger() {
    setRunning(true);
    try {
      const run = await runTracking({
        paper_ids: paperIds.slice(0, 5),
        max_candidates: 3,
        max_imports: 0,
        force: true,
      });
      setLastRun(run);
      await load();
    } catch (cause) {
      setError(cause);
    } finally {
      setRunning(false);
    }
  }

  const run = lastRun ?? status?.latest_run ?? null;
  const scheduler = status?.scheduler_details ?? null;

  return (
    <div>
      <div className="sg-form">
        <button
          className="sg-btn"
          type="button"
          disabled={running}
          onClick={trigger}
        >
          {running ? "正在追踪…" : "立即运行一次追踪"}
        </button>
        <button className="sg-btn sg-btn--ghost" type="button" onClick={load}>
          刷新状态
        </button>
      </div>

      {scheduler ? (
        <p className="sg-mono">
          调度：{scheduler.mechanism} · 启用 {String(scheduler.enabled)} · 活动{" "}
          {String(scheduler.active)} · 间隔 {scheduler.interval_seconds ?? "—"} 秒 ·
          已自动运行 {scheduler.run_count ?? 0} 次
        </p>
      ) : null}
      <p className="sg-mono">
        去重日志 {status?.dedup_records?.length ?? 0} 条 · 默认间隔{" "}
        {status?.default_interval_seconds ?? "—"} 秒
      </p>

      {run ? (
        <div className="sg-kv">
          <div className="sg-stream__done">
            <span className="sg-tag sg-tag--muted">最近一次运行</span>
            {statusTag(run.status)}
            <span className="sg-mono">run_id {run.run_id.slice(0, 8)}</span>
            <span className="sg-mono">
              耗时 {run.duration_seconds ?? "—"} 秒
            </span>
            <span className="sg-mono">候选 {run.candidate_count}</span>
            <span className="sg-mono">新增 {run.imported_count}</span>
            <span className="sg-mono">重复 {run.duplicate_count}</span>
            <span className="sg-mono">失败 {run.failed_count}</span>
          </div>
          <p className="sg-mono">
            {run.started_at ?? "—"} → {run.finished_at ?? "—"}
          </p>

          {run.errors.length > 0 ? (
            <div>
              <p className="sg-mono">失败原因（后端原文）：</p>
              {run.errors.map((item, index) => (
                <pre className="sg-synthesis" key={index}>
                  {`${item.error_code}：${item.message}`}
                </pre>
              ))}
            </div>
          ) : (
            <p className="sg-mono">本次没有记录到失败原因。</p>
          )}

          {run.queries.length > 0 ? (
            <p className="sg-mono">
              查询 {run.queries.length} 条（真实公开 arXiv Atom 查询）
            </p>
          ) : null}
        </div>
      ) : (
        <p className="sg-mono">还没有运行记录，点上方按钮立即运行一次。</p>
      )}

      {error ? <ErrorState title="追踪状态取数失败" error={error} /> : null}
    </div>
  );
}

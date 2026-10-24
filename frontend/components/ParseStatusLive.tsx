"use client";

import { useEffect, useRef, useState } from "react";
import { clientFetchParseStatus } from "@/lib/api";
import type { ParseStatus, ParseStatusValue } from "@/lib/types";

const TERMINAL: ParseStatusValue[] = ["completed", "failed"];
const POLL_INTERVAL_MS = 2000;
/** 轮询上限，防止状态一直不终态时死循环 */
const MAX_ATTEMPTS = 60;

const STATUS_TAG: Record<string, string> = {
  queued: "sg-tag sg-tag--muted",
  parsing: "sg-tag sg-tag--info",
  ocr: "sg-tag sg-tag--info",
  indexing: "sg-tag sg-tag--info",
  completed: "sg-tag sg-tag--success",
  failed: "sg-tag sg-tag--error",
};

type StopReason =
  | { kind: "running" }
  | { kind: "terminal"; status: ParseStatusValue }
  | { kind: "limit" }
  | { kind: "error"; message: string };

export default function ParseStatusLive({
  paperId,
  initial,
}: {
  paperId: string;
  initial: ParseStatus;
}) {
  const [status, setStatus] = useState<ParseStatus>(initial);
  const [attempts, setAttempts] = useState(0);
  const [stop, setStop] = useState<StopReason>({ kind: "running" });
  const stopRef = useRef(stop);
  stopRef.current = stop;

  useEffect(() => {
    if (TERMINAL.includes(initial.status)) {
      setStop({ kind: "terminal", status: initial.status });
      return;
    }

    let cancelled = false;
    let count = 0;

    const timer = setInterval(async () => {
      if (cancelled) return;
      if (stopRef.current.kind !== "running") {
        clearInterval(timer);
        return;
      }

      count += 1;
      setAttempts(count);

      try {
        const next = await clientFetchParseStatus(paperId);
        if (cancelled) return;
        setStatus(next);
        if (TERMINAL.includes(next.status)) {
          setStop({ kind: "terminal", status: next.status });
          clearInterval(timer);
        } else if (count >= MAX_ATTEMPTS) {
          setStop({ kind: "limit" });
          clearInterval(timer);
        }
      } catch (error) {
        if (cancelled) return;
        setStop({
          kind: "error",
          message: error instanceof Error ? error.message : String(error),
        });
        clearInterval(timer);
      }
    }, POLL_INTERVAL_MS);

    return () => {
      cancelled = true;
      clearInterval(timer);
    };
  }, [paperId, initial.status]);

  return (
    <div>
      <dl className="sg-kv">
        <dt>paper_id</dt>
        <dd className="sg-mono">{status.paper_id}</dd>
        <dt>状态 status</dt>
        <dd>
          <span className={STATUS_TAG[status.status] ?? "sg-tag"}>
            {status.status}
          </span>
        </dd>
        <dt>进度 progress</dt>
        <dd>
          <div className="sg-progress">
            <div
              className={
                status.status === "failed"
                  ? "sg-progress__bar sg-progress__bar--failed"
                  : "sg-progress__bar"
              }
              style={{ width: `${status.progress}%` }}
            />
          </div>
          <span className="sg-num">{status.progress}%</span>
        </dd>
        <dt>当前阶段 current_stage</dt>
        <dd>{status.current_stage}</dd>
        <dt>错误码 error_code</dt>
        <dd className="sg-mono">{status.error_code ?? "—"}</dd>
        <dt>错误信息 error_message</dt>
        <dd>{status.error_message ?? "—"}</dd>
      </dl>

      <p className="sg-poll">
        {stop.kind === "running" ? (
          <span className="sg-tag sg-tag--info">
            轮询中 · 已请求 {attempts} 次 · 每 {POLL_INTERVAL_MS / 1000} 秒一次
          </span>
        ) : null}
        {stop.kind === "terminal" ? (
          <span className="sg-tag sg-tag--success">
            已停止轮询：状态进入终态 {stop.status}（共请求 {attempts} 次）
          </span>
        ) : null}
        {stop.kind === "limit" ? (
          <span className="sg-tag sg-tag--warning">
            已停止轮询：达到上限 {MAX_ATTEMPTS} 次，状态仍为 {status.status}
          </span>
        ) : null}
        {stop.kind === "error" ? (
          <span className="sg-tag sg-tag--error">
            已停止轮询：请求失败 {stop.message}
          </span>
        ) : null}
      </p>
    </div>
  );
}

"use client";

import { useEffect, useRef, useState } from "react";
import { clientFetchParseStatus } from "@/lib/api";
import type { ParseStatus, ParseStatusValue } from "@/lib/types";
import Diagnostics from "./Diagnostics";
import AsyncStatus from "./AsyncStatus";

const TERMINAL: ParseStatusValue[] = ["completed", "failed"];
const POLL_INTERVAL_MS = 2000;
/** 轮询上限，防止状态一直不终态时死循环 */
const MAX_ATTEMPTS = 60;
const STATUS_LABELS: Record<ParseStatusValue, string> = { queued: "排队中", parsing: "正在解析", ocr: "正在识别扫描文本", indexing: "正在建立索引", completed: "解析完成", failed: "解析失败" };

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
        <dt>解析状态</dt>
        <dd>
          <span className={STATUS_TAG[status.status] ?? "sg-tag"}>
            {STATUS_LABELS[status.status]}
          </span>
        </dd>
        <dt>处理进度</dt>
        <dd>
          <div className="sg-progress" role="progressbar" aria-label="解析进度" aria-valuenow={status.progress} aria-valuemin={0} aria-valuemax={100}>
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
        <dt>当前阶段</dt>
        <dd>{status.current_stage}</dd>
        {status.error_message ? <><dt>失败原因</dt><dd>{status.error_message}</dd></> : null}
      </dl>
      {!TERMINAL.includes(status.status) && stop.kind !== "error" ? <AsyncStatus label="解析仍在进行，已完成内容会继续保留。" rows={2} /> : null}
      <Diagnostics summary="解析诊断（原始状态与轮询记录）"><p>paper_id: {status.paper_id}</p><p>status: {status.status} · error_code: {status.error_code ?? "null"}</p><p>已请求 {attempts} 次，间隔 {POLL_INTERVAL_MS / 1000} 秒，上限 {MAX_ATTEMPTS} 次。</p></Diagnostics>

      <p className="sg-poll">
        {stop.kind === "running" ? (
          <span className="sg-tag sg-tag--info">
            正在更新解析状态
          </span>
        ) : null}
        {stop.kind === "terminal" ? (
          <span className={stop.status === "failed" ? "sg-tag sg-tag--error" : "sg-tag sg-tag--success"}>
            {STATUS_LABELS[stop.status]}，状态更新已停止
          </span>
        ) : null}
        {stop.kind === "limit" ? (
          <span className="sg-tag sg-tag--warning">
            自动更新已暂停，解析状态仍为{STATUS_LABELS[status.status]}。可刷新详情重新查看。
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

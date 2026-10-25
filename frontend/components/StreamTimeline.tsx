"use client";

import { useCallback, useRef, useState } from "react";
import {
  isFinalAnswer,
  streamQa,
  type DoneEvent,
  type ModeEvent,
  type NodeEndEvent,
  type NodeStartEvent,
  type SseEnvelope,
  type TokenEvent,
  type ToolEndEvent,
  type ToolStartEvent,
} from "@/lib/sse";
import type { QAAnswer } from "@/lib/types";
import ErrorState from "./ErrorState";
import QaAnswerView from "./QaAnswerView";

interface NodeRow {
  key: string;
  node: string;
  attempt: number;
  elapsed: number | null;
  evidence: number | null;
  status: string | null;
  validation: boolean | null;
  validationError: string | null;
  reason: string | null;
}

interface ToolRow {
  key: string;
  tool_name: string;
  origin: string;
  tool_call_id: string | null;
  attempt: number;
  elapsed: number | null;
  status: string | null;
  evidence: number | null;
}

const NODE_LABEL: Record<string, string> = {
  plan: "规划 plan",
  retrieve: "检索 retrieve",
  qa: "问答 qa",
  validate: "校验 validate",
  refuse: "拒答 refuse",
};

function ms(seconds: number | null): string {
  if (seconds === null) return "—";
  return `${(seconds * 1000).toFixed(1)} ms`;
}

function nodeLabel(node: string): string {
  return NODE_LABEL[node] ?? node;
}

/**
 * 问答流式时间线。
 *
 * 三条纪律：
 * 1. 事件到一条画一条：节点开始/完成、轮次、耗时、证据数、驳回原因原文都实时推进；
 * 2. token 增量始终标注「草稿（未校验）」，只有 final 到达后才展示最终答案；
 * 3. error 到达即展示错误原文并结束，不编造答案。
 */
export default function StreamTimeline({
  paperId,
  question,
}: {
  paperId: string;
  question: string;
}) {
  const [running, setRunning] = useState(false);
  const [mode, setMode] = useState<ModeEvent | null>(null);
  const [nodes, setNodes] = useState<NodeRow[]>([]);
  const [tools, setTools] = useState<ToolRow[]>([]);
  const [draft, setDraft] = useState("");
  const [tokenCount, setTokenCount] = useState(0);
  const [answer, setAnswer] = useState<QAAnswer | null>(null);
  const [done, setDone] = useState<DoneEvent | null>(null);
  const [errorText, setErrorText] = useState<string | null>(null);
  const [errorEnvelope, setErrorEnvelope] = useState<unknown>(null);
  const [eventCount, setEventCount] = useState(0);
  const abortRef = useRef<AbortController | null>(null);

  const handleEvent = useCallback((envelope: SseEnvelope) => {
    setEventCount((count) => count + 1);

    switch (envelope.event) {
      case "mode":
        setMode(envelope.data as ModeEvent);
        break;

      case "node_start": {
        const data = envelope.data as NodeStartEvent;
        setNodes((rows) => [
          ...rows,
          {
            key: `${data.node}-${data.attempt}-${rows.length}`,
            node: data.node,
            attempt: data.attempt,
            elapsed: null,
            evidence: data.evidence_count,
            status: null,
            validation: null,
            validationError: null,
            reason: null,
          },
        ]);
        break;
      }

      case "node_end": {
        const data = envelope.data as NodeEndEvent;
        setNodes((rows) => {
          const index = [...rows]
            .reverse()
            .findIndex(
              (row) =>
                row.node === data.node &&
                row.attempt === data.attempt &&
                row.status === null,
            );
          if (index === -1) return rows;
          const target = rows.length - 1 - index;
          const next = [...rows];
          next[target] = {
            ...next[target],
            elapsed: data.elapsed_seconds,
            evidence: data.evidence_count,
            status: data.status,
            validation: data.validation,
            validationError: data.validation_error,
            reason: data.reason ?? null,
          };
          return next;
        });
        break;
      }

      case "tool_start": {
        const data = envelope.data as ToolStartEvent;
        setTools((rows) => [
          ...rows,
          {
            key: `${data.tool_call_id ?? data.tool_name}-${rows.length}`,
            tool_name: data.tool_name,
            origin: data.origin,
            tool_call_id: data.tool_call_id,
            attempt: data.attempt,
            elapsed: null,
            status: null,
            evidence: null,
          },
        ]);
        break;
      }

      case "tool_end": {
        const data = envelope.data as ToolEndEvent;
        setTools((rows) => {
          const index = [...rows]
            .reverse()
            .findIndex((row) => row.tool_call_id === data.tool_call_id);
          if (index === -1) return rows;
          const target = rows.length - 1 - index;
          const next = [...rows];
          next[target] = {
            ...next[target],
            elapsed: data.elapsed_seconds,
            status: data.status,
            evidence: data.evidence_count,
          };
          return next;
        });
        break;
      }

      case "token": {
        const data = envelope.data as TokenEvent;
        setDraft((text) => text + data.delta);
        setTokenCount((count) => count + 1);
        break;
      }

      case "final": {
        if (isFinalAnswer(envelope.data)) {
          setAnswer(envelope.data);
        }
        break;
      }

      case "error": {
        const data = envelope.data as {
          error_code?: string;
          message?: string;
        };
        setErrorText(
          `${data.error_code ?? "UNKNOWN"}：${data.message ?? "（无消息）"}`,
        );
        setErrorEnvelope(envelope.data);
        break;
      }

      case "done":
        setDone(envelope.data as DoneEvent);
        break;

      default:
        break;
    }
  }, []);

  async function start() {
    if (!paperId || !question.trim()) return;
    const controller = new AbortController();
    abortRef.current = controller;

    setRunning(true);
    setMode(null);
    setNodes([]);
    setTools([]);
    setDraft("");
    setTokenCount(0);
    setAnswer(null);
    setDone(null);
    setErrorText(null);
    setErrorEnvelope(null);
    setEventCount(0);

    try {
      await streamQa(paperId, question, {
        onEvent: handleEvent,
        signal: controller.signal,
      });
    } catch (cause) {
      if (cause instanceof DOMException && cause.name === "AbortError") {
        // 用户主动停止，不编造结果
      } else if (cause instanceof Error) {
        setErrorText(cause.message);
        setErrorEnvelope({ error_code: "CLIENT_ERROR", message: cause.message });
      } else {
        setErrorText(String(cause));
      }
    } finally {
      setRunning(false);
    }
  }

  function stop() {
    abortRef.current?.abort();
    setRunning(false);
  }

  return (
    <div className="sg-stream">
      <div className="sg-form">
        <button
          className="sg-btn"
          type="button"
          disabled={running || !question.trim()}
          onClick={start}
        >
          {running ? "流式进行中…" : "开始流式问答"}
        </button>
        {running ? (
          <button className="sg-btn sg-btn--ghost" type="button" onClick={stop}>
            停止
          </button>
        ) : null}
        <span className="sg-mono">
          已收事件 {eventCount} 条 · 节点 {nodes.length} · 工具 {tools.length}
        </span>
      </div>

      {mode ? (
        <div className="sg-stream__mode">
          {mode.fallback_reason || !mode.token_streaming ? (
            <span className="sg-tag sg-tag--warning">
              回落模式、非 token 流式
            </span>
          ) : (
            <span className="sg-tag sg-tag--info">
              真实上游 token 增量（未校验草稿）
            </span>
          )}
          <span className="sg-mono">mode {mode.mode}</span>
          <span className="sg-mono">
            token_streaming {String(mode.token_streaming)}
          </span>
          <span className="sg-mono">
            fallback_reason {mode.fallback_reason ?? "null"}
          </span>
          <p className="sg-mono">{mode.message}</p>
        </div>
      ) : null}

      {errorText ? (
        <div>
          <ErrorState
            title="流式问答出错（已结束，不编造答案）"
            error={errorText}
          />
          {errorEnvelope && typeof errorEnvelope === "object" ? (
            <pre className="sg-synthesis">
              {JSON.stringify(errorEnvelope, null, 2)}
            </pre>
          ) : null}
        </div>
      ) : null}

      <h4 className="sg-qa__sub">节点时间线（随流实时推进）</h4>
      {nodes.length === 0 ? (
        <p className="sg-mono">尚无节点事件。</p>
      ) : (
        <table className="sg-table">
          <thead>
            <tr>
              <th>节点</th>
              <th className="sg-num">轮次</th>
              <th className="sg-num">耗时</th>
              <th className="sg-num">证据数</th>
              <th>状态</th>
              <th>校验</th>
            </tr>
          </thead>
          <tbody>
            {nodes.map((row) => (
              <tr key={row.key}>
                <td className="sg-mono">{nodeLabel(row.node)}</td>
                <td className="sg-num">{row.attempt}</td>
                <td className="sg-num">
                  {row.elapsed === null ? "进行中" : ms(row.elapsed)}
                </td>
                <td className="sg-num">{row.evidence ?? "—"}</td>
                <td>
                  {row.status === null ? (
                    <span className="sg-tag sg-tag--info">执行中</span>
                  ) : row.status === "completed" ? (
                    <span className="sg-tag sg-tag--muted">completed</span>
                  ) : (
                    <span className="sg-tag sg-tag--error">{row.status}</span>
                  )}
                </td>
                <td>
                  {row.validation === true ? (
                    <span className="sg-tag sg-tag--success">通过</span>
                  ) : row.validation === false ? (
                    <span className="sg-tag sg-tag--error">
                      驳回
                      {row.validationError ? `：${row.validationError}` : ""}
                    </span>
                  ) : row.reason ? (
                    <span className="sg-tag sg-tag--error">{row.reason}</span>
                  ) : (
                    <span className="sg-mono">—</span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      <p className="sg-mono">
        说明：node_end.status=completed 只表示节点执行完，是否通过要看「校验」列，
        不以 completed 冒充通过。
      </p>

      <h4 className="sg-qa__sub">工具调用（随流实时推进）</h4>
      {tools.length === 0 ? (
        <p className="sg-mono">
          尚无工具调用事件
          {mode?.fallback_reason
            ? "（回落模式不构造模型客户端，不会虚构模型工具调用）。"
            : "。"}
        </p>
      ) : (
        <table className="sg-table">
          <thead>
            <tr>
              <th>工具名</th>
              <th>来源</th>
              <th className="sg-num">轮次</th>
              <th>tool_call_id</th>
              <th className="sg-num">返回证据数</th>
              <th className="sg-num">耗时</th>
              <th>状态</th>
            </tr>
          </thead>
          <tbody>
            {tools.map((row) => (
              <tr key={row.key}>
                <td className="sg-mono">{row.tool_name}</td>
                <td>
                  <span
                    className={
                      row.origin === "model_function_call"
                        ? "sg-tag sg-tag--info"
                        : "sg-tag sg-tag--muted"
                    }
                  >
                    {row.origin}
                  </span>
                </td>
                <td className="sg-num">{row.attempt}</td>
                <td className="sg-mono">{row.tool_call_id ?? "—"}</td>
                <td className="sg-num">{row.evidence ?? "—"}</td>
                <td className="sg-num">{ms(row.elapsed)}</td>
                <td>
                  {row.status === null ? (
                    <span className="sg-tag sg-tag--info">执行中</span>
                  ) : (
                    <span
                      className={
                        row.status === "succeeded"
                          ? "sg-tag sg-tag--success"
                          : "sg-tag sg-tag--error"
                      }
                    >
                      {row.status}
                    </span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      <h4 className="sg-qa__sub">
        增量区
        <span className="sg-tag sg-tag--warning">草稿（未校验）</span>
      </h4>
      {tokenCount === 0 ? (
        <p className="sg-mono">
          本次没有 token 增量
          {mode?.fallback_reason
            ? "（回落模式不发 token，最终答案整段到达）。"
            : "。"}
        </p>
      ) : (
        <>
          <p className="sg-mono">
            已收 {tokenCount} 条 token 增量，channel=model_json_draft、verified=false。
            以下是未校验的 JSON 草稿片段，不是最终答案，也不等于 final.answer 的逐字拼接；
            事件条数不是服务商 token 数。
          </p>
          <pre className="sg-synthesis">{draft}</pre>
        </>
      )}

      <h4 className="sg-qa__sub">最终答案（仅 final 事件到达后展示）</h4>
      {answer ? (
        <QaAnswerView answer={answer} />
      ) : (
        <p className="sg-mono">
          尚未收到 final 事件
          {done ? `（流已结束，done.status=${done.status}）` : "。"}
          {" "}未收到 final 时不展示任何答案，草稿不得冒充最终答案。
        </p>
      )}

      {done ? (
        <div className="sg-stream__done">
          <span className="sg-tag sg-tag--muted">流已结束</span>
          <span className="sg-mono">done.status {done.status}</span>
          <span className="sg-mono">
            token_streaming {String(done.token_streaming)}
          </span>
          <span className="sg-mono">
            fallback_reason {done.fallback_reason ?? "null"}
          </span>
          {done.metadata?.attempts !== undefined ? (
            <span className="sg-mono">
              attempts {done.metadata.attempts} / {done.metadata.max_attempts}
            </span>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}

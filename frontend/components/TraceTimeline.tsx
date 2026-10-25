import type { AgentMeta, ModelCallRow, TraceRow } from "@/lib/types";

const NODE_LABEL: Record<string, string> = {
  plan: "规划 plan",
  retrieve: "检索 retrieve",
  qa: "问答 qa",
  validate: "校验 validate",
  refuse: "拒答 refuse",
  retry: "重试 retry",
  done: "完成 done",
};

function ms(seconds: number | null): string {
  if (seconds === null || seconds === undefined) return "—";
  return `${(seconds * 1000).toFixed(1)} ms`;
}

function nodeLabel(node: string): string {
  return NODE_LABEL[node] ?? node;
}

/**
 * 编排时间线。
 * 按轨迹原始顺序展示，不做美化：
 * - 校验未通过的轮次原样展示驳回原因原文；
 * - 第 N 轮失败、第 M 轮通过这种重试过程完整保留，不只画最后成功一次；
 * - 没有工具调用或模型调用时如实写明原因，不补空壳。
 */
export default function TraceTimeline({
  agentMeta,
  qaMeta,
}: {
  agentMeta: AgentMeta | null;
  qaMeta: { model_calls: ModelCallRow[] } | null;
}) {
  if (!agentMeta) {
    return (
      <div className="sg-note">
        <span className="sg-tag sg-tag--warning">本次未返回编排元数据</span>
        <p className="sg-note__text">
          后端仅在带 <code>?agent=true</code> 时返回{" "}
          <code>X-ScholarGraph-Agent-Meta</code>。当前未勾选编排模式，
          因此没有轨迹可展示，页面不补任何假轨迹。
        </p>
      </div>
    );
  }

  const { trace, tool_calls, model_calls, attempts, max_attempts } = agentMeta;
  const rounds = groupByAttempt(trace);
  const totalMs = trace.reduce((sum, row) => sum + row.elapsed_seconds, 0);

  return (
    <div className="sg-trace">
      <dl className="sg-kv">
        <dt>编排引擎 engine</dt>
        <dd className="sg-mono">{agentMeta.engine}</dd>
        <dt>轮次 attempts</dt>
        <dd className="sg-mono">
          {attempts} / 上限 {max_attempts}
        </dd>
        <dt>轨迹节点数</dt>
        <dd className="sg-mono">{trace.length}</dd>
        <dt>轨迹总耗时</dt>
        <dd className="sg-mono">{ms(totalMs)}</dd>
        <dt>最终校验 validated</dt>
        <dd>
          {agentMeta.validated ? (
            <span className="sg-tag sg-tag--success">通过</span>
          ) : (
            <span className="sg-tag sg-tag--error">未通过</span>
          )}
        </dd>
        <dt>回落原因 fallback_reason</dt>
        <dd>
          {agentMeta.fallback_reason ? (
            <span className="sg-tag sg-tag--warning">
              {agentMeta.fallback_reason}
            </span>
          ) : (
            <span className="sg-mono">null</span>
          )}
        </dd>
        <dt>检查点 / 外部追踪</dt>
        <dd className="sg-mono">
          checkpointing {String(agentMeta.checkpointing)} · external_tracing{" "}
          {String(agentMeta.external_tracing)}
        </dd>
      </dl>

      {agentMeta.fallback_reason ? (
        <div className="sg-note">
          <span className="sg-tag sg-tag--warning">本次走回落路径</span>
          <p className="sg-note__text">
            编排图已执行，但模型未配置/不可用，回落到本地确定性摘录器。
            下面展示的是<strong>真实发生的</strong>节点轨迹与耗时，不是模型推理过程。
          </p>
        </div>
      ) : null}

      <h4 className="sg-qa__sub">节点时间线（按原始顺序，含失败轮次）</h4>
      <div className="sg-timeline">
        {trace.map((row, index) => (
          <div className="sg-timeline__row" key={`${row.node}-${row.attempt}-${index}`}>
            <div className="sg-timeline__dot" aria-hidden="true" />
            <div className="sg-timeline__body">
              <div className="sg-timeline__head">
                <strong>{nodeLabel(row.node)}</strong>
                <span className="sg-mono">第 {row.attempt} 轮</span>
                <span className="sg-mono">{ms(row.elapsed_seconds)}</span>
                <span className="sg-mono">证据 {row.evidence_count} 条</span>
                {row.validation === true ? (
                  <span className="sg-tag sg-tag--success">校验通过</span>
                ) : null}
                {row.validation === false ? (
                  <span className="sg-tag sg-tag--error">校验驳回</span>
                ) : null}
              </div>
              {row.validation_error ? (
                <p className="sg-timeline__reason">
                  驳回原因原文：{row.validation_error}
                </p>
              ) : null}
              {row.fallback_reason ? (
                <p className="sg-mono">
                  该节点回落原因：{row.fallback_reason}
                </p>
              ) : null}
            </div>
          </div>
        ))}
      </div>

      <h4 className="sg-qa__sub">分轮小结</h4>
      <table className="sg-table">
        <thead>
          <tr>
            <th className="sg-num">轮次</th>
            <th>节点序列</th>
            <th className="sg-num">本轮耗时</th>
            <th className="sg-num">证据数</th>
            <th>校验结果</th>
          </tr>
        </thead>
        <tbody>
          {rounds.map((round) => (
            <tr key={round.attempt}>
              <td className="sg-num">{round.attempt}</td>
              <td className="sg-mono">{round.rows.map((r) => r.node).join(" → ")}</td>
              <td className="sg-num">{ms(round.total)}</td>
              <td className="sg-num">{round.evidence}</td>
              <td>
                {round.validation === true ? (
                  <span className="sg-tag sg-tag--success">通过</span>
                ) : round.validation === false ? (
                  <span className="sg-tag sg-tag--error">
                    驳回{round.error ? `：${round.error}` : ""}
                  </span>
                ) : (
                  <span className="sg-tag sg-tag--muted">未进入校验</span>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      <h4 className="sg-qa__sub">工具调用 tool_calls</h4>
      {tool_calls.length === 0 ? (
        <p className="sg-mono">
          本次无工具调用。工具调用由模型通过 Function Calling 发起；
          当前编排走回落路径时没有模型参与，因此不会产出 tool_calls，
          页面不补造记录。
        </p>
      ) : (
        <table className="sg-table">
          <thead>
            <tr>
              <th className="sg-num">#</th>
              <th>工具名</th>
              <th>来源 origin</th>
              <th className="sg-num">轮次</th>
              <th>tool_call_id</th>
              <th>入参摘要</th>
              <th>返回摘要（证据数）</th>
              <th className="sg-num">耗时</th>
              <th>状态</th>
            </tr>
          </thead>
          <tbody>
            {tool_calls.map((call, index) => (
              <tr key={`${call.tool_call_id}-${index}`}>
                <td className="sg-num">{index + 1}</td>
                <td className="sg-mono">{call.tool_name}</td>
                <td>
                  <span
                    className={
                      call.origin === "model_function_call"
                        ? "sg-tag sg-tag--info"
                        : "sg-tag sg-tag--muted"
                    }
                  >
                    {call.origin}
                  </span>
                </td>
                <td className="sg-num">{call.attempt}</td>
                <td className="sg-mono">{call.tool_call_id ?? "—"}</td>
                <td className="sg-mono">
                  {JSON.stringify(call.arguments_summary)}
                </td>
                <td className="sg-mono">
                  {JSON.stringify(call.return_summary)}
                </td>
                <td className="sg-num">{ms(call.elapsed_seconds)}</td>
                <td>
                  <span
                    className={
                      call.status === "succeeded"
                        ? "sg-tag sg-tag--success"
                        : "sg-tag sg-tag--error"
                    }
                  >
                    {call.status}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      <ModelCallsTable
        title="编排内模型调用 model_calls（X-ScholarGraph-Agent-Meta）"
        calls={model_calls}
        emptyHint="本次编排没有模型调用（回落路径下 client 为空）。"
      />
      <ModelCallsTable
        title="模型调用统计（X-ScholarGraph-QA-Meta）"
        calls={qaMeta?.model_calls ?? []}
        emptyHint={
          qaMeta
            ? "后端返回了该响应头，但本次没有模型调用记录。"
            : "后端未返回 X-ScholarGraph-QA-Meta（仅 SCHOLAR_GRAPH_QA_MODE=deepseek 且配置 Key 时返回），页面不编造服务商、模型名与耗时。"
        }
      />
    </div>
  );
}

function ModelCallsTable({
  title,
  calls,
  emptyHint,
}: {
  title: string;
  calls: ModelCallRow[];
  emptyHint: string;
}) {
  return (
    <>
      <h4 className="sg-qa__sub">{title}</h4>
      {calls.length === 0 ? (
        <p className="sg-mono">{emptyHint}</p>
      ) : (
        <table className="sg-table">
          <thead>
            <tr>
              <th className="sg-num">#</th>
              <th>服务商 provider</th>
              <th>模型名 model</th>
              <th>阶段 phase</th>
              <th className="sg-num">耗时</th>
              <th className="sg-num">提示 token</th>
              <th className="sg-num">完成 token</th>
              <th className="sg-num">总 token</th>
              <th className="sg-num">HTTP</th>
              <th>状态</th>
            </tr>
          </thead>
          <tbody>
            {calls.map((call, index) => (
              <tr key={index}>
                <td className="sg-num">{index + 1}</td>
                <td className="sg-mono">{call.provider}</td>
                <td className="sg-mono">{call.model}</td>
                <td className="sg-mono">{call.phase}</td>
                <td className="sg-num">{ms(call.elapsed_seconds)}</td>
                <td className="sg-num">{call.prompt_tokens ?? "—"}</td>
                <td className="sg-num">{call.completion_tokens ?? "—"}</td>
                <td className="sg-num">{call.total_tokens ?? "—"}</td>
                <td className="sg-num">{call.http_status ?? "—"}</td>
                <td>
                  <span
                    className={
                      call.status === "ok" || call.status === "succeeded"
                        ? "sg-tag sg-tag--success"
                        : "sg-tag sg-tag--error"
                    }
                  >
                    {call.status}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </>
  );
}

interface Round {
  attempt: number;
  rows: TraceRow[];
  total: number;
  evidence: number;
  validation: boolean | null;
  error: string | null;
}

function groupByAttempt(trace: TraceRow[]): Round[] {
  const map = new Map<number, Round>();
  for (const row of trace) {
    const attempt = row.attempt || 0;
    const existing = map.get(attempt);
    if (existing) {
      existing.rows.push(row);
      existing.total += row.elapsed_seconds;
      existing.evidence = row.evidence_count;
      if (row.validation !== null) {
        existing.validation = row.validation;
        existing.error = row.validation_error;
      }
    } else {
      map.set(attempt, {
        attempt,
        rows: [row],
        total: row.elapsed_seconds,
        evidence: row.evidence_count,
        validation: row.validation,
        error: row.validation_error,
      });
    }
  }
  return [...map.values()].sort((a, b) => a.attempt - b.attempt);
}

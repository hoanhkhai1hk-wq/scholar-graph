"use client";

import { useState } from "react";
import Link from "next/link";
import { askQuestion, comparePapers } from "@/lib/api";
import type {
  AgentMeta,
  CompareResult,
  PaperMeta,
  QAAnswer,
  QaMeta,
} from "@/lib/types";
import PaperPicker from "@/components/PaperPicker";
import QaAnswerView from "@/components/QaAnswerView";
import ErrorState from "@/components/ErrorState";
import TraceTimeline from "@/components/TraceTimeline";
import StreamTimeline from "@/components/StreamTimeline";

type State =
  | { kind: "idle" }
  | { kind: "loading" }
  | {
      kind: "qa";
      answer: QAAnswer;
      agentMeta: AgentMeta | null;
      qaMeta: QaMeta | null;
    }
  | {
      kind: "compare";
      result: CompareResult;
      agentMeta: AgentMeta | null;
      qaMeta: QaMeta | null;
    }
  | { kind: "error"; error: unknown };

export default function QaWorkspace({ papers }: { papers: PaperMeta[] }) {
  const [selected, setSelected] = useState<string[]>([]);
  const [question, setQuestion] = useState("");
  const [useAgent, setUseAgent] = useState(true);
  const [transport, setTransport] = useState<"sync" | "stream">("stream");
  const [state, setState] = useState<State>({ kind: "idle" });

  const isCompare = selected.length >= 2;
  // 流式端点目前只有单篇问答；跨篇对比走同步端点
  const useStream = transport === "stream" && !isCompare;

  async function submit() {
    if (selected.length === 0 || !question.trim()) return;
    if (useStream) return; // 流式由 StreamTimeline 自己的按钮驱动
    setState({ kind: "loading" });
    try {
      if (selected.length === 1) {
        const response = await askQuestion(selected[0], question.trim(), {
          agent: useAgent,
        });
        setState({
          kind: "qa",
          answer: response.data,
          agentMeta: response.agentMeta,
          qaMeta: response.qaMeta,
        });
      } else {
        const response = await comparePapers(selected, question.trim(), {
          agent: useAgent,
        });
        setState({
          kind: "compare",
          result: response.data,
          agentMeta: response.agentMeta,
          qaMeta: response.qaMeta,
        });
      }
    } catch (error) {
      setState({ kind: "error", error });
    }
  }

  return (
    <>
      <section className="sg-section">
        <div className="sg-section__head">
          <h2 className="sg-section__title">提问</h2>
          <span className="sg-section__hint">
            {isCompare
              ? `已选多篇 → POST /api/v1/compare${useAgent ? "?agent=true" : ""}`
              : `选中一篇 → POST /api/v1/papers/{id}/qa${useAgent ? "?agent=true" : ""}`}
          </span>
        </div>

        <div className="sg-form sg-form--inline">
          <label className="sg-checkbox">
            <input
              type="radio"
              name="transport"
              checked={transport === "stream"}
              onChange={() => setTransport("stream")}
            />
            流式 SSE（<code>POST /qa/stream</code>）
          </label>
          <label className="sg-checkbox">
            <input
              type="radio"
              name="transport"
              checked={transport === "sync"}
              onChange={() => setTransport("sync")}
            />
            同步（<code>POST /qa</code> 或 <code>/compare</code>）
          </label>
          <label className="sg-checkbox">
            <input
              type="checkbox"
              checked={useAgent}
              onChange={(event) => setUseAgent(event.target.checked)}
            />
            同步时启用 LangGraph 编排（<code>?agent=true</code>）
          </label>
        </div>
        <p className="sg-mono">
          流式用 fetch + ReadableStream 逐事件读取（原生 EventSource 只发 GET，
          本端点是 POST）。草稿与最终答案严格分开：只有 final 事件到达后才展示经校验的
          QAAnswer。跨篇对比暂用同步端点。
        </p>

        <PaperPicker
          papers={papers}
          selected={selected}
          onChange={setSelected}
          multiple
          label="选择论文（1 篇走单篇问答，2–10 篇走跨篇对比）"
        />

        <div className="sg-form">
          <textarea
            className="sg-input sg-input--area"
            placeholder="输入问题，例如：本文样本量是多少？"
            value={question}
            onChange={(event) => setQuestion(event.target.value)}
          />
          <button
            className="sg-btn"
            type="button"
            disabled={
              selected.length === 0 ||
              !question.trim() ||
              state.kind === "loading" ||
              useStream
            }
            onClick={submit}
          >
            {state.kind === "loading" ? "请求中…" : isCompare ? "跨篇对比" : "提问"}
          </button>
        </div>

        {selected.length > 10 ? (
          <p className="sg-tag sg-tag--error">
            跨篇对比最多 10 篇，当前已选 {selected.length} 篇
          </p>
        ) : null}
        {useStream && isCompare ? (
          <p className="sg-tag sg-tag--warning">
            流式端点目前只有单篇问答，已选多篇请改用同步方式。
          </p>
        ) : null}
      </section>

      {useStream ? (
        <section className="sg-section">
          <div className="sg-section__head">
            <h2 className="sg-section__title">流式问答（SSE）</h2>
            <span className="sg-section__hint">
              POST /api/v1/papers/{"{id}"}/qa/stream
            </span>
          </div>
          {selected.length === 1 ? (
            <StreamTimeline paperId={selected[0]} question={question} />
          ) : (
            <p className="sg-mono">
              请先在上方勾选且仅勾选一篇论文，再开始流式问答。
            </p>
          )}
        </section>
      ) : null}

      {state.kind === "qa" ? (
        <section className="sg-section">
          <div className="sg-section__head">
            <h2 className="sg-section__title">单篇问答结果</h2>
            <span className="sg-section__hint">QAAnswer</span>
          </div>
          <QaAnswerView answer={state.answer} />
          <h3 className="sg-subhead">思考过程时间线</h3>
          <TraceTimeline agentMeta={state.agentMeta} qaMeta={state.qaMeta} />
        </section>
      ) : null}

      {state.kind === "compare" ? (
        <section className="sg-section">
          <div className="sg-section__head">
            <h2 className="sg-section__title">跨篇对比结果</h2>
            <span className="sg-section__hint">
              evidence_table / per_paper / synthesis
            </span>
          </div>

          <h3 className="sg-subhead">证据表</h3>
          {state.result.evidence_table.length === 0 ? (
            <p>后端返回空证据表。</p>
          ) : (
            <table className="sg-table">
              <thead>
                <tr>
                  <th>编号</th>
                  <th className="sg-num">对应第几篇</th>
                  <th>锚点</th>
                  <th>原文摘录</th>
                </tr>
              </thead>
              <tbody>
                {state.result.evidence_table.map((row) => (
                  <tr key={row.evidence_id}>
                    <td className="sg-mono">{row.evidence_id}</td>
                    <td className="sg-num">{row.per_paper_index}</td>
                    <td className="sg-mono">
                      p.{row.anchor.page_number} · {row.anchor.chunk_id}
                    </td>
                    <td>
                      {row.quotes.map((quote, index) => (
                        <p className="sg-prose" key={index}>
                          {quote}
                        </p>
                      ))}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}

          <h3 className="sg-subhead">逐篇回答</h3>
          {state.result.per_paper.map((answer, index) => (
            <QaAnswerView
              key={index}
              answer={answer}
              title={`第 ${index + 1} 篇 · ${
                papers.find((p) => p.id === selected[index])?.title ??
                selected[index]
              }`}
            />
          ))}

          <h3 className="sg-subhead">综合</h3>
          <pre className="sg-synthesis">{state.result.synthesis}</pre>

          <h3 className="sg-subhead">思考过程时间线</h3>
          <TraceTimeline agentMeta={state.agentMeta} qaMeta={state.qaMeta} />
        </section>
      ) : null}

      {state.kind === "error" ? (
        <section className="sg-section">
          <div className="sg-section__head">
            <h2 className="sg-section__title">请求失败</h2>
            <span className="sg-section__hint">未取得后端数据</span>
          </div>
          <ErrorState title="问答请求失败" error={state.error} />
        </section>
      ) : null}

      <section className="sg-section">
        <p className="sg-mono">
          说明：问答为本地确定性原文摘录，默认不调用真实模型；
          拒答时原样展示拒答原因与原文纠错，不改写为答案。
          更多细节见 <Link href="/">能力索引</Link>。
        </p>
      </section>
    </>
  );
}

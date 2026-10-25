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
  const [state, setState] = useState<State>({ kind: "idle" });

  const isCompare = selected.length >= 2;

  async function submit() {
    if (selected.length === 0 || !question.trim()) return;
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

        <label className="sg-checkbox">
          <input
            type="checkbox"
            checked={useAgent}
            onChange={(event) => setUseAgent(event.target.checked)}
          />
          使用 LangGraph 编排（<code>?agent=true</code>）
        </label>
        <p className="sg-mono">
          勾选后后端返回 X-ScholarGraph-Agent-Meta，前端据此画出 plan → retrieve →
          qa → validate 的轨迹时间线；不勾选则没有轨迹可展示。
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
            disabled={selected.length === 0 || !question.trim() || state.kind === "loading"}
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
      </section>

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

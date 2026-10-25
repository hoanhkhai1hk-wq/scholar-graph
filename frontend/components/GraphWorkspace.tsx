"use client";

import { useState } from "react";
import { clientFetchGraph } from "@/lib/api";
import type { GraphView, PaperMeta } from "@/lib/types";
import PaperPicker from "@/components/PaperPicker";
import ErrorState from "@/components/ErrorState";
import GraphCanvas from "@/components/GraphCanvas";

type State =
  | { kind: "idle" }
  | { kind: "loading" }
  | { kind: "ok"; data: GraphView }
  | { kind: "error"; error: unknown };

const LEVEL_TAG: Record<string, string> = {
  cornerstone: "sg-tag sg-tag--success",
  derived: "sg-tag sg-tag--info",
  isolated: "sg-tag sg-tag--muted",
};

const LEVEL_LABEL: Record<string, string> = {
  cornerstone: "基石",
  derived: "衍生",
  isolated: "孤立",
};

export default function GraphWorkspace({ papers }: { papers: PaperMeta[] }) {
  const [selected, setSelected] = useState<string[]>([]);
  const [state, setState] = useState<State>({ kind: "idle" });

  async function submit() {
    if (selected.length === 0) return;
    setState({ kind: "loading" });
    try {
      const data = await clientFetchGraph(selected);
      setState({ kind: "ok", data });
    } catch (error) {
      setState({ kind: "error", error });
    }
  }

  const data = state.kind === "ok" ? state.data : null;

  return (
    <>
      <section className="sg-section">
        <div className="sg-section__head">
          <h2 className="sg-section__title">选择论文集合</h2>
          <span className="sg-section__hint">
            GET /api/v1/graph?paper_ids=…（1–100 篇）
          </span>
        </div>

        <PaperPicker
          papers={papers}
          selected={selected}
          onChange={setSelected}
          multiple
          label="选择论文"
        />

        <div className="sg-form">
          <button
            className="sg-btn"
            type="button"
            disabled={selected.length === 0 || state.kind === "loading"}
            onClick={submit}
          >
            {state.kind === "loading"
              ? "请求中…"
              : `生成图谱（已选 ${selected.length}）`}
          </button>
        </div>
      </section>

      {state.kind === "error" ? (
        <section className="sg-section">
          <div className="sg-section__head">
            <h2 className="sg-section__title">图谱取数失败</h2>
            <span className="sg-section__hint">未取得后端数据</span>
          </div>
          <ErrorState title="图谱请求失败" error={state.error} />
        </section>
      ) : null}

      {data ? (
        <>
          <section className="sg-section">
            <div className="sg-section__head">
              <h2 className="sg-section__title">图谱画布</h2>
              <span className="sg-section__hint">
                只画已核验边 · 孤立节点可见 · 点节点进详情
              </span>
            </div>
            <GraphCanvas graph={data} />
          </section>

          <section className="sg-section">
            <div className="sg-section__head">
              <h2 className="sg-section__title">节点与分层（附表）</h2>
              <span className="sg-section__hint">
                基石 {data.layers.cornerstone.length} · 衍生{" "}
                {data.layers.derived.length} · 孤立{" "}
                {data.layers.isolated.length}
              </span>
            </div>

            <table className="sg-table">
              <thead>
                <tr>
                  <th>论文</th>
                  <th className="sg-num">年份</th>
                  <th className="sg-num">PageRank</th>
                  <th>层级</th>
                </tr>
              </thead>
              <tbody>
                {data.nodes.map((node) => (
                  <tr key={node.paper_id}>
                    <td>
                      <div>{node.title ?? "（标题未提取）"}</div>
                      <div className="sg-mono">{node.paper_id}</div>
                    </td>
                    <td className="sg-num">{node.year ?? "—"}</td>
                    <td className="sg-num">{node.pagerank}</td>
                    <td>
                      <span className={LEVEL_TAG[node.level] ?? "sg-tag"}>
                        {LEVEL_LABEL[node.level] ?? node.level} · {node.level}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>

            <p className="sg-mono">
              分层规则：无 verified 入/出边为 isolated；有 verified 入边且分值
              &gt; 1/N 为 cornerstone；其余为 derived。1/N 是本局域图的均匀基线，
              不是论文质量阈值。
            </p>
          </section>

          <section className="sg-section">
            <div className="sg-section__head">
              <h2 className="sg-section__title">引用边</h2>
              <span className="sg-section__hint">
                引用方 → 被引方；无锚点边原样标 unverified
              </span>
            </div>

            {data.edges.length === 0 ? (
              <p>后端返回 0 条边。</p>
            ) : (
              <table className="sg-table">
                <thead>
                  <tr>
                    <th>引用方</th>
                    <th>被引方</th>
                    <th>状态</th>
                    <th>锚点</th>
                  </tr>
                </thead>
                <tbody>
                  {data.edges.map((edge, index) => (
                    <tr
                      key={`${edge.from_paper_id}-${edge.to_paper_id}-${index}`}
                    >
                      <td className="sg-mono">{edge.from_paper_id}</td>
                      <td className="sg-mono">{edge.to_paper_id}</td>
                      <td>
                        <span
                          className={
                            edge.status === "verified"
                              ? "sg-tag sg-tag--success"
                              : "sg-tag sg-tag--warning"
                          }
                        >
                          {edge.status}
                        </span>
                      </td>
                      <td>
                        {edge.anchor ? (
                          <span className="sg-mono">
                            p.{edge.anchor.page_number} ·{" "}
                            {edge.anchor.chunk_id}
                          </span>
                        ) : (
                          <span className="sg-tag sg-tag--warning">
                            无锚点 · 不可验证
                          </span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </section>

          <section className="sg-section">
            <div className="sg-section__head">
              <h2 className="sg-section__title">未来方向</h2>
              <span className="sg-section__hint">
                已排除与保留分开列，保留的带更晚论文锚点
              </span>
            </div>

            <h3 className="sg-subhead">
              待探索 worth_exploring（{data.future_work.worth_exploring.length}）
            </h3>
            <FutureWorkTable items={data.future_work.worth_exploring} />

            <h3 className="sg-subhead">
              已排除 excluded（{data.future_work.excluded.length}）
            </h3>
            <FutureWorkTable
              items={data.future_work.excluded}
              hint="排除依据：更晚论文的「已解决」声明所在 Chunk 必须有 verified 引用指向原论文。"
            />

            <h3 className="sg-subhead">
              无法判定 unverifiable（{data.future_work.unverifiable.length}）
            </h3>
            <FutureWorkTable
              items={data.future_work.unverifiable}
              hint="年份未知或无法比较时间，既不当作已解决，也不断言未解决。"
            />

            <h3 className="sg-subhead">判定记录 checks</h3>
            {data.future_work.checks.length === 0 ? (
              <p className="sg-mono">无判定记录。</p>
            ) : (
              <table className="sg-table">
                <thead>
                  <tr>
                    <th>方向</th>
                    <th>候选论文</th>
                    <th>判定</th>
                    <th>原因</th>
                  </tr>
                </thead>
                <tbody>
                  {data.future_work.checks.map((check, index) => (
                    <tr key={`${check.direction_id}-${index}`}>
                      <td className="sg-mono">{check.direction_id}</td>
                      <td className="sg-mono">{check.candidate_paper_id}</td>
                      <td>
                        <span
                          className={
                            check.decision === "excluded"
                              ? "sg-tag sg-tag--success"
                              : "sg-tag sg-tag--muted"
                          }
                        >
                          {check.decision}
                        </span>
                      </td>
                      <td>{check.reason}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </section>

          <section className="sg-section">
            <div className="sg-section__head">
              <h2 className="sg-section__title">诊断信息</h2>
              <span className="sg-section__hint">diagnostics</span>
            </div>

            <dl className="sg-kv">
              <dt>阻尼 damping</dt>
              <dd className="sg-mono">{data.diagnostics.pagerank.damping}</dd>
              <dt>收敛容差 tolerance</dt>
              <dd className="sg-mono">{data.diagnostics.pagerank.tolerance}</dd>
              <dt>迭代 iterations</dt>
              <dd className="sg-mono">
                {data.diagnostics.pagerank.iterations} / 上限{" "}
                {data.diagnostics.pagerank.max_iterations}
              </dd>
              <dt>残差 residual</dt>
              <dd className="sg-mono">{data.diagnostics.pagerank.residual}</dd>
              <dt>verified 论文对</dt>
              <dd className="sg-mono">
                {data.diagnostics.pagerank.verified_pair_count}
              </dd>
              <dt>均匀基线 uniform_baseline</dt>
              <dd className="sg-mono">
                {data.diagnostics.pagerank.uniform_baseline}
              </dd>
            </dl>

            <h3 className="sg-subhead">
              未解析引用 unresolved_references（
              {data.diagnostics.unresolved_references.length}）
            </h3>
            {data.diagnostics.unresolved_references.length === 0 ? (
              <p className="sg-mono">无未解析引用。</p>
            ) : (
              <table className="sg-table">
                <thead>
                  <tr>
                    <th>论文</th>
                    <th>条目</th>
                    <th>原因</th>
                  </tr>
                </thead>
                <tbody>
                  {data.diagnostics.unresolved_references.map((item, index) => (
                    <tr key={`${item.ref_id}-${index}`}>
                      <td className="sg-mono">{item.paper_id}</td>
                      <td className="sg-mono">{item.ref_id}</td>
                      <td>{item.reason}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </section>
        </>
      ) : null}
    </>
  );
}

function FutureWorkTable({
  items,
  hint,
}: {
  items: GraphView["future_work"]["worth_exploring"];
  hint?: string;
}) {
  if (items.length === 0) {
    return <p className="sg-mono">无条目。</p>;
  }
  return (
    <>
      {hint ? <p className="sg-mono">{hint}</p> : null}
      <table className="sg-table">
        <thead>
          <tr>
            <th>方向</th>
            <th>来源锚点</th>
            <th>更晚论文解决声明</th>
          </tr>
        </thead>
        <tbody>
          {items.map((item) => (
            <tr key={item.direction_id}>
              <td>
                <div>{item.topic}</div>
                <div className="sg-mono">{item.direction_id}</div>
              </td>
              <td>
                {item.source.anchors.length > 0 ? (
                  item.source.anchors.map((anchor, index) => (
                    <div className="sg-mono" key={index}>
                      p.{anchor.page_number} · {anchor.chunk_id}
                    </div>
                  ))
                ) : (
                  <span className="sg-tag sg-tag--warning">无锚点</span>
                )}
              </td>
              <td>
                {item.resolutions.length === 0 ? (
                  <span className="sg-mono">—</span>
                ) : (
                  item.resolutions.map((resolution, index) =>
                    resolution.anchors.map((anchor, i) => (
                      <div className="sg-mono" key={`${index}-${i}`}>
                        {resolution.answer.slice(0, 80)} · p.
                        {anchor.page_number} · {anchor.chunk_id}
                      </div>
                    )),
                  )
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </>
  );
}

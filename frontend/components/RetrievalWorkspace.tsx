"use client";

import { useState } from "react";
import {
  fetchArxiv,
  fetchRecommendations,
  searchRetrieval,
} from "@/lib/api";
import type {
  FetchResult,
  PaperMeta,
  Paged,
  RecommendationItem,
  SearchHit,
} from "@/lib/types";
import PaperPicker from "@/components/PaperPicker";
import ErrorState from "@/components/ErrorState";
import TrackingPanel from "@/components/TrackingPanel";
import EmptyState from "@/components/EmptyState";

type SearchState =
  | { kind: "idle" }
  | { kind: "loading" }
  | {
      kind: "ok";
      data: Paged<SearchHit>;
      meta: { mode: string | null; vectorStatus: string | null; reason: string | null };
    }
  | { kind: "error"; error: unknown };

type FetchState =
  | { kind: "idle" }
  | { kind: "loading" }
  | { kind: "ok"; data: FetchResult }
  | { kind: "error"; error: unknown };

type RecoState =
  | { kind: "idle" }
  | { kind: "loading" }
  | { kind: "ok"; data: Paged<RecommendationItem>; reason: string | null }
  | { kind: "error"; error: unknown };

/** 检索模式按后端响应头原值展示，不得把词法说成向量 */
function modeLabel(mode: string | null): string {
  if (mode === "lexical") return "词法兜底 lexical";
  if (mode === "bge_m3_hybrid") return "BGE-M3 稠密/稀疏混合 bge_m3_hybrid";
  return mode ?? "未返回";
}

function reasonLabel(reason: string | null): string {
  const map: Record<string, string> = {
    OK: "正常返回",
    EMPTY_CORPUS: "语料为空",
    NO_MATCHING_CHUNKS: "无匹配分块",
    PAGE_OUT_OF_RANGE: "分页越界",
    NO_CANDIDATES: "无候选论文",
  };
  return reason ? (map[reason] ?? reason) : "未返回";
}

export default function RetrievalWorkspace({
  papers,
}: {
  papers: PaperMeta[];
}) {
  const [question, setQuestion] = useState("");
  const [targets, setTargets] = useState<string[]>([]);
  const [minRelevance, setMinRelevance] = useState(0);
  const [search, setSearch] = useState<SearchState>({ kind: "idle" });

  const [fetchTitle, setFetchTitle] = useState("");
  const [fetched, setFetched] = useState<FetchState>({ kind: "idle" });

  const [seed, setSeed] = useState<string[]>([]);
  const [asOfYear, setAsOfYear] = useState("");
  const [reco, setReco] = useState<RecoState>({ kind: "idle" });

  async function runSearch() {
    if (!question.trim()) return;
    setSearch({ kind: "loading" });
    try {
      const result = await searchRetrieval({
        question: question.trim(),
        paper_ids: targets.length > 0 ? targets : undefined,
        page: 1,
        page_size: 20,
        min_relevance: minRelevance,
      });
      setSearch({
        kind: "ok",
        data: result.data,
        meta: result.meta,
      });
    } catch (error) {
      setSearch({ kind: "error", error });
    }
  }

  async function runFetch() {
    if (!fetchTitle.trim()) return;
    setFetched({ kind: "loading" });
    try {
      const data = await fetchArxiv({ title: fetchTitle.trim() });
      setFetched({ kind: "ok", data });
    } catch (error) {
      setFetched({ kind: "error", error });
    }
  }

  async function runRecommend() {
    if (seed.length === 0) return;
    setReco({ kind: "loading" });
    try {
      const result = await fetchRecommendations({
        paperId: seed[0],
        asOfYear: asOfYear ? Number(asOfYear) : undefined,
        page: 1,
        pageSize: 20,
      });
      setReco({ kind: "ok", data: result.data, reason: result.reason });
    } catch (error) {
      setReco({ kind: "error", error });
    }
  }

  return (
    <>
      {/* 检索 */}
      <section className="sg-section">
        <div className="sg-section__head">
          <h2 className="sg-section__title">检索</h2>
          <span className="sg-section__hint">POST /api/v1/retrieval/search</span>
        </div>

        <PaperPicker
          papers={papers}
          selected={targets}
          onChange={setTargets}
          multiple
          label="限定论文范围（不勾选则检索全部已落盘论文）"
        />

        <div className="sg-form">
          <input
            className="sg-input"
            type="text"
            placeholder="检索问题，例如：样本量"
            value={question}
            onChange={(event) => setQuestion(event.target.value)}
          />
          <label className="sg-field">
            最小相关度
            <input
              className="sg-input sg-input--narrow"
              type="number"
              min={0}
              max={1}
              step={0.05}
              value={minRelevance}
              onChange={(event) => setMinRelevance(Number(event.target.value))}
            />
          </label>
          <button
            className="sg-btn"
            type="button"
            disabled={!question.trim() || search.kind === "loading"}
            onClick={runSearch}
          >
            {search.kind === "loading" ? "检索中…" : "检索"}
          </button>
        </div>

        {search.kind === "ok" ? (
          <>
            <div className="sg-response-meta">
              <span className="sg-tag sg-tag--info">
                检索模式：{modeLabel(search.meta.mode)}
              </span>
              <span className="sg-tag sg-tag--muted">
                向量状态：{search.meta.vectorStatus ?? "未返回"}
              </span>
              <span className="sg-tag sg-tag--muted">
                结果原因：{reasonLabel(search.meta.reason)}
              </span>
            </div>
            <p className="sg-mono">
              以上三项直接取自后端响应头 X-ScholarGraph-Search-Mode /
              Vector-Status / Search-Reason，前端不改写；
              relevance 是排序分值，不是正确性概率。
            </p>

            {search.data.items.length === 0 ? (
              <EmptyState
                title="没有命中任何段落"
                hint="换一个更具体的关键词，或确认已经选中了论文。当前检索走本地词法（IDF 加权余弦），不做语义改写，冷门表述可能命中不到。"
                aside={`total=${search.data.total} · mode=${search.meta.mode ?? "—"}`}
              />
            ) : (
              <table className="sg-table">
                <thead>
                  <tr>
                    <th className="sg-num">相关度</th>
                    <th>检索方式</th>
                    <th>锚点</th>
                    <th>原文</th>
                  </tr>
                </thead>
                <tbody>
                  {search.data.items.map((hit) => (
                    <tr key={hit.chunk.chunk_id}>
                      <td className="sg-num">{hit.relevance}</td>
                      <td>
                        <span className="sg-tag">{hit.retrieval_method}</span>
                      </td>
                      <td className="sg-mono">
                        p.{hit.anchor.page_number} · {hit.anchor.chunk_id}
                      </td>
                      <td>
                        <p className="sg-prose">{hit.chunk.text}</p>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </>
        ) : null}
        {search.kind === "error" ? (
          <ErrorState title="检索请求失败" error={search.error} />
        ) : null}
      </section>

      {/* 公开抓取 */}
      <section className="sg-section">
        <div className="sg-section__head">
          <h2 className="sg-section__title">公开抓取（arXiv）</h2>
          <span className="sg-section__hint">POST /api/v1/retrieval/fetch</span>
        </div>

        <div className="sg-form">
          <input
            className="sg-input"
            type="text"
            placeholder="论文标题，按标题归一后完全匹配才接受"
            value={fetchTitle}
            onChange={(event) => setFetchTitle(event.target.value)}
          />
          <button
            className="sg-btn"
            type="button"
            disabled={!fetchTitle.trim() || fetched.kind === "loading"}
            onClick={runFetch}
          >
            {fetched.kind === "loading" ? "抓取中…" : "抓取并解析"}
          </button>
        </div>

        {fetched.kind === "ok" ? (
          <dl className="sg-kv">
            <dt>succeeded</dt>
            <dd className="sg-mono">{String(fetched.data.succeeded)}</dd>
            <dt>metadata（公开元数据）</dt>
            <dd className="sg-mono">
              {fetched.data.metadata
                ? `${fetched.data.metadata.id} · ${fetched.data.metadata.title ?? "—"}`
                : "null"}
            </dd>
            <dt>paper（已解析论文）</dt>
            <dd className="sg-mono">
              {fetched.data.paper ? fetched.data.paper.id : "null"}
            </dd>
            <dt>initial_parse_status</dt>
            <dd className="sg-mono">
              {fetched.data.initial_parse_status
                ? `${fetched.data.initial_parse_status.status} ${fetched.data.initial_parse_status.progress}%`
                : "null"}
            </dd>
            <dt>parse_status</dt>
            <dd className="sg-mono">
              {fetched.data.parse_status
                ? `${fetched.data.parse_status.status} ${fetched.data.parse_status.progress}%`
                : "null"}
            </dd>
            <dt>error</dt>
            <dd>
              {fetched.data.error
                ? `${fetched.data.error.error_code} · ${fetched.data.error.message}`
                : "null"}
            </dd>
          </dl>
        ) : null}
        {fetched.kind === "error" ? (
          <ErrorState title="抓取请求失败" error={fetched.error} />
        ) : null}

        <p className="sg-mono">
          抓取优先按 arXiv 基号精确查 Atom API，其次裸 DOI，最后标题完全匹配；
          不使用相似标题冒充。失败时 error 为统一三字段错误体，不虚构排队记录。
        </p>
      </section>

      {/* 定期追踪 */}
      <section className="sg-section">
        <div className="sg-section__head">
          <h2 className="sg-section__title">arXiv 定期追踪</h2>
          <span className="sg-section__hint">
            GET /retrieval/tracking/status · POST /retrieval/tracking/run
          </span>
        </div>
        <TrackingPanel paperIds={papers.map((paper) => paper.id)} />
      </section>

      {/* 推荐 */}
      <section className="sg-section">
        <div className="sg-section__head">
          <h2 className="sg-section__title">智能推荐</h2>
          <span className="sg-section__hint">
            GET /api/v1/recommendations · 评分 module-four-v1
          </span>
        </div>

        <PaperPicker
          papers={papers}
          selected={seed}
          onChange={setSeed}
          label="选择种子论文（单选）"
        />

        <div className="sg-form">
          <label className="sg-field">
            as_of_year
            <input
              className="sg-input sg-input--narrow"
              type="number"
              placeholder="默认当前 UTC 年份"
              value={asOfYear}
              onChange={(event) => setAsOfYear(event.target.value)}
            />
          </label>
          <button
            className="sg-btn"
            type="button"
            disabled={seed.length === 0 || reco.kind === "loading"}
            onClick={runRecommend}
          >
            {reco.kind === "loading" ? "计算中…" : "获取推荐"}
          </button>
        </div>

        {reco.kind === "ok" ? (
          <>
            <div className="sg-response-meta">
              <span className="sg-tag sg-tag--muted">
                响应头原因：{reasonLabel(reco.reason)}
              </span>
            </div>

            {reco.data.items.length === 0 ? (
              <EmptyState
                title="暂时没有可推荐的论文"
                hint="先选一篇种子论文：推荐从它的引用邻居与主题词出发。库里论文太少时也会没有候选。"
                aside={`total=${reco.data.total}`}
              />
            ) : (
              <table className="sg-table">
                <thead>
                  <tr>
                    <th>候选论文</th>
                    <th className="sg-num">含金量 score</th>
                    <th>分项 signals</th>
                    <th>理由 reasons</th>
                    <th>缺失项</th>
                  </tr>
                </thead>
                <tbody>
                  {reco.data.items.map((item) => (
                    <tr key={item.paper.id}>
                      <td>
                        <div>{item.paper.title ?? "（标题未提取）"}</div>
                        <div className="sg-mono">{item.paper.id}</div>
                        <div className="sg-mono">
                          {item.scoring_version} · as_of_year {item.as_of_year}
                        </div>
                      </td>
                      <td className="sg-num">{item.score}</td>
                      <td className="sg-mono">
                        G {item.signals.graph_neighbor ?? "null"} · P{" "}
                        {item.signals.pagerank_normalized ?? "null"} · T{" "}
                        {item.signals.recency ?? "null"} · C{" "}
                        {item.signals.github_link ?? "null"}
                      </td>
                      <td>
                        {item.reasons.length === 0 ? (
                          <span className="sg-mono">—</span>
                        ) : (
                          item.reasons.map((reason, index) => (
                            <div key={index}>
                              <span className="sg-tag sg-tag--muted">
                                {reason.signal}
                              </span>{" "}
                              {reason.text}
                              {reason.evidence.length > 0 ? (
                                <div className="sg-mono">
                                  {reason.evidence.join("；")}
                                </div>
                              ) : null}
                            </div>
                          ))
                        )}
                      </td>
                      <td>
                        {item.missing_signals.length === 0 ? (
                          <span className="sg-mono">无</span>
                        ) : (
                          item.missing_signals.map((signal) => (
                            <span className="sg-tag sg-tag--warning" key={signal}>
                              {signal}
                            </span>
                          ))
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}

            <p className="sg-mono">
              评分公式：score = 100 × (0.40·G + 0.35·P + 0.15·T + 0.10·C)，
              缺失项按 0 贡献不重新分配权重。该公式是可复核的启发式排序，
              未以用户数据训练，也未完成推荐质量评估。
            </p>
          </>
        ) : null}
        {reco.kind === "error" ? (
          <ErrorState title="推荐请求失败" error={reco.error} />
        ) : null}
      </section>
    </>
  );
}

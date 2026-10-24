"use client";

import { useState } from "react";
import {
  generateFramework,
  generateReview,
  uploadCsvChart,
} from "@/lib/api";
import type {
  ChartOutput,
  FrameworkOutline,
  PaperMeta,
  ReviewDraft,
} from "@/lib/types";
import PaperPicker from "@/components/PaperPicker";
import ErrorState from "@/components/ErrorState";

type FrameworkState =
  | { kind: "idle" }
  | { kind: "loading" }
  | { kind: "ok"; data: FrameworkOutline }
  | { kind: "error"; error: unknown };

type ReviewState =
  | { kind: "idle" }
  | { kind: "loading" }
  | { kind: "ok"; data: ReviewDraft }
  | { kind: "error"; error: unknown };

type ChartState =
  | { kind: "idle" }
  | { kind: "loading" }
  | { kind: "ok"; data: ChartOutput }
  | { kind: "error"; error: unknown };

const CHECK_TAG: Record<string, string> = {
  passed: "sg-tag sg-tag--success",
  failed: "sg-tag sg-tag--error",
  unverifiable: "sg-tag sg-tag--warning",
  not_applicable: "sg-tag sg-tag--muted",
};

export default function WritingWorkspace({
  papers,
}: {
  papers: PaperMeta[];
}) {
  const [selected, setSelected] = useState<string[]>([]);
  const [framework, setFramework] = useState<FrameworkState>({ kind: "idle" });
  const [requirements, setRequirements] = useState("");
  const [review, setReview] = useState<ReviewState>({ kind: "idle" });

  const [csvFile, setCsvFile] = useState<File | null>(null);
  const [valueColumns, setValueColumns] = useState("");
  const [chartType, setChartType] = useState("bar");
  const [xColumn, setXColumn] = useState("");
  const [caption, setCaption] = useState("");
  const [chart, setChart] = useState<ChartState>({ kind: "idle" });

  const outline = framework.kind === "ok" ? framework.data : null;

  async function runFramework() {
    if (selected.length === 0) return;
    setFramework({ kind: "loading" });
    setReview({ kind: "idle" });
    try {
      const data = await generateFramework(selected);
      setFramework({ kind: "ok", data });
    } catch (error) {
      setFramework({ kind: "error", error });
    }
  }

  async function runReview() {
    if (!outline || selected.length === 0) return;
    setReview({ kind: "loading" });
    try {
      const data = await generateReview({
        paper_ids: selected,
        framework: outline,
        requirements: requirements.trim()
          ? requirements
              .split("\n")
              .map((item) => item.trim())
              .filter(Boolean)
              .slice(0, 10)
          : [],
      });
      setReview({ kind: "ok", data });
    } catch (error) {
      setReview({ kind: "error", error });
    }
  }

  async function runChart() {
    if (!csvFile || !valueColumns.trim()) return;
    setChart({ kind: "loading" });
    try {
      const data = await uploadCsvChart({
        file: csvFile,
        value_columns: valueColumns
          .split(",")
          .map((item) => item.trim())
          .filter(Boolean),
        chart_type: chartType,
        x_column: xColumn.trim() ? xColumn.trim() : undefined,
        caption: caption.trim() ? caption.trim() : undefined,
      });
      setChart({ kind: "ok", data });
    } catch (error) {
      setChart({ kind: "error", error });
    }
  }

  return (
    <>
      <section className="sg-section">
        <div className="sg-section__head">
          <h2 className="sg-section__title">综述框架</h2>
          <span className="sg-section__hint">POST /api/v1/frameworks</span>
        </div>

        <PaperPicker
          papers={papers}
          selected={selected}
          onChange={(ids) => {
            setSelected(ids);
            setFramework({ kind: "idle" });
            setReview({ kind: "idle" });
          }}
          multiple
          label="选择论文（1–100 篇）"
        />

        <div className="sg-form">
          <button
            className="sg-btn"
            type="button"
            disabled={selected.length === 0 || framework.kind === "loading"}
            onClick={runFramework}
          >
            {framework.kind === "loading" ? "生成中…" : "生成框架"}
          </button>
        </div>

        {framework.kind === "error" ? (
          <ErrorState title="框架生成失败" error={framework.error} />
        ) : null}

        {outline ? (
          <>
            <p className="sg-mono">
              schema_version {outline.schema_version} · 章节{" "}
              {outline.chapters.length}
            </p>
            {outline.chapters.map((chapter) => (
              <div className="sg-chapter" key={chapter.chapter_id}>
                <h3 className="sg-subhead">
                  {chapter.title}
                  <span className="sg-tag sg-tag--muted">{chapter.kind}</span>
                </h3>
                <p className="sg-mono">{chapter.chapter_id}</p>
                <p className="sg-mono">
                  归属论文：{chapter.paper_ids.join("；")}
                </p>

                <h4 className="sg-qa__sub">待写要点（原文摘录）</h4>
                <ul className="sg-anchor-list">
                  {chapter.writing_points.map((point, index) => (
                    <li key={index}>
                      <p className="sg-prose">{point.text}</p>
                      <span className="sg-mono">
                        {point.anchor
                          ? `p.${point.anchor.page_number} · ${point.anchor.chunk_id}`
                          : "无锚点"}
                      </span>
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </>
        ) : null}
      </section>

      <section className="sg-section">
        <div className="sg-section__head">
          <h2 className="sg-section__title">摘录草稿</h2>
          <span className="sg-section__hint">POST /api/v1/reviews</span>
        </div>

        <p className="sg-note__text">
          草稿为原文摘录与数字回溯的结果，<strong>不是模型生成的成文</strong>；
          最终成文由用户完成。requires 框架与当前集合完全一致，
          被改写的框架会返回 422。
        </p>

        <div className="sg-form">
          <textarea
            className="sg-input sg-input--area"
            placeholder="额外要求（每行一条，最多 10 条，可留空）"
            value={requirements}
            onChange={(event) => setRequirements(event.target.value)}
          />
          <button
            className="sg-btn"
            type="button"
            disabled={!outline || review.kind === "loading"}
            onClick={runReview}
          >
            {review.kind === "loading" ? "生成中…" : "生成摘录草稿"}
          </button>
        </div>

        {review.kind === "error" ? (
          <ErrorState title="草稿生成失败" error={review.error} />
        ) : null}

        {review.kind === "ok" ? (
          <>
            <p className="sg-mono">
              mode {review.data.mode} · 不可验证要点{" "}
              {review.data.unverifiable_count}
            </p>
            {review.data.chapters.map((chapter) => (
              <div className="sg-chapter" key={chapter.chapter_id}>
                <h3 className="sg-subhead">{chapter.title}</h3>
                <table className="sg-table">
                  <thead>
                    <tr>
                      <th>要点</th>
                      <th>状态</th>
                      <th>锚点</th>
                      <th>数字校验</th>
                      <th>对应用户要求</th>
                    </tr>
                  </thead>
                  <tbody>
                    {chapter.points.map((point, index) => (
                      <tr key={index}>
                        <td>
                          <p className="sg-prose">{point.text}</p>
                        </td>
                        <td>
                          <span
                            className={
                              point.status === "verified"
                                ? "sg-tag sg-tag--success"
                                : "sg-tag sg-tag--warning"
                            }
                          >
                            {point.status}
                          </span>
                        </td>
                        <td>
                          {point.anchors.length === 0 ? (
                            <span className="sg-tag sg-tag--warning">
                              无锚点
                            </span>
                          ) : (
                            point.anchors.map((anchor, i) => (
                              <div className="sg-mono" key={i}>
                                p.{anchor.page_number} · {anchor.chunk_id}
                              </div>
                            ))
                          )}
                        </td>
                        <td>
                          <span
                            className={
                              CHECK_TAG[point.numeric_fact_check.status] ??
                              "sg-tag"
                            }
                          >
                            {point.numeric_fact_check.status}
                          </span>
                          <div className="sg-mono">
                            checks {point.numeric_fact_check.checks.length}
                          </div>
                        </td>
                        <td>{point.requirement ?? "—"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ))}
          </>
        ) : null}
      </section>

      <section className="sg-section">
        <div className="sg-section__head">
          <h2 className="sg-section__title">CSV 图表</h2>
          <span className="sg-section__hint">POST /api/v1/charts/csv</span>
        </div>

        <div className="sg-form">
          <input
            className="sg-input"
            type="file"
            accept=".csv,text/csv"
            onChange={(event) => {
              setCsvFile(event.target.files?.[0] ?? null);
              setChart({ kind: "idle" });
            }}
          />
          <label className="sg-field">
            value_columns（逗号分隔）
            <input
              className="sg-input"
              type="text"
              placeholder="samples"
              value={valueColumns}
              onChange={(event) => setValueColumns(event.target.value)}
            />
          </label>
          <label className="sg-field">
            chart_type
            <select
              className="sg-input"
              value={chartType}
              onChange={(event) => setChartType(event.target.value)}
            >
              <option value="bar">bar</option>
              <option value="line">line</option>
              <option value="scatter">scatter</option>
              <option value="histogram">histogram</option>
            </select>
          </label>
          <label className="sg-field">
            x_column（可选）
            <input
              className="sg-input sg-input--narrow"
              type="text"
              value={xColumn}
              onChange={(event) => setXColumn(event.target.value)}
            />
          </label>
          <label className="sg-field">
            caption（可选，受限语法）
            <input
              className="sg-input"
              type="text"
              placeholder="CSV values: 12, 18."
              value={caption}
              onChange={(event) => setCaption(event.target.value)}
            />
          </label>
          <button
            className="sg-btn"
            type="button"
            disabled={!csvFile || !valueColumns.trim() || chart.kind === "loading"}
            onClick={runChart}
          >
            {chart.kind === "loading" ? "生成中…" : "生成图表"}
          </button>
        </div>

        {chart.kind === "error" ? (
          <ErrorState title="图表生成失败" error={chart.error} />
        ) : null}

        {chart.kind === "ok" ? (
          <>
            <p className="sg-mono">
              chart_id {chart.data.chart_id} · chart_type{" "}
              {chart.data.chart_type}
            </p>

            {chart.data.image_ref ? (
              /* image_ref 是后端真实生成的 PNG data URI，不是占位图 */
              // eslint-disable-next-line @next/next/no-img-element
              <img
                className="sg-chart-image"
                src={chart.data.image_ref}
                alt={chart.data.caption}
              />
            ) : null}

            <h4 className="sg-qa__sub">图注（受限语法）</h4>
            <p className="sg-prose">{chart.data.caption}</p>

            <h4 className="sg-qa__sub">系列</h4>
            <table className="sg-table">
              <thead>
                <tr>
                  <th>系列</th>
                  <th>数值</th>
                </tr>
              </thead>
              <tbody>
                {chart.data.series.map((series) => (
                  <tr key={series.name}>
                    <td className="sg-mono">{series.name}</td>
                    <td className="sg-mono">{series.values.join(", ")}</td>
                  </tr>
                ))}
              </tbody>
            </table>

            <h4 className="sg-qa__sub">图注数字与 CSV 的回溯关系</h4>
            <table className="sg-table">
              <thead>
                <tr>
                  <th className="sg-num">数值</th>
                  <th>CSV 源</th>
                  <th className="sg-num">行号</th>
                  <th>列名</th>
                  <th>校验</th>
                </tr>
              </thead>
              <tbody>
                {chart.data.numeric_checks.map((check, index) => (
                  <tr key={index}>
                    <td className="sg-num">{check.value}</td>
                    <td className="sg-mono">{check.csv_anchor.csv_ref}</td>
                    <td className="sg-num">
                      {check.csv_anchor.row_number}
                    </td>
                    <td className="sg-mono">
                      {check.csv_anchor.column_name}
                    </td>
                    <td>
                      <span
                        className={
                          check.verified
                            ? "sg-tag sg-tag--success"
                            : "sg-tag sg-tag--warning"
                        }
                      >
                        {String(check.verified)}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            <p className="sg-mono">
              csv_ref 为上传 CSV 原始字节的 SHA-256，行号按 CSV 逻辑记录从 2 起；
              源 CSV 由上传者保留供复核，后端不新增资源服务路径。
            </p>
          </>
        ) : null}
      </section>
    </>
  );
}

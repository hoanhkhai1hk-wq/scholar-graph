"use client";

import { useMemo, useState } from "react";
import { translatePaper } from "@/lib/api";
import type { Chunk, TranslateResponse, TranslateScope } from "@/lib/types";
import ErrorState from "./ErrorState";
import BilingualPane from "./BilingualPane";

interface Result {
  scope: TranslateScope;
  label: string;
  response: TranslateResponse;
}

/**
 * 四个翻译入口：摘要 / 章节 / 选区 / 全文。
 *
 * 两条如实规则：
 * 1. 选区翻译当前是**整 Chunk**，不是逐词或字符级选区，界面写明；
 * 2. 无 Key 时后端返回 502 UPSTREAM_ERROR，前端原样展示错误，不编造译文。
 */
export default function TranslatePanel({
  paperId,
  chunks,
}: {
  paperId: string;
  chunks: Chunk[];
}) {
  const [loading, setLoading] = useState<TranslateScope | null>(null);
  const [result, setResult] = useState<Result | null>(null);
  const [error, setError] = useState<{ scope: string; error: unknown } | null>(
    null,
  );
  const [section, setSection] = useState<string>("");
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [markdownMode, setMarkdownMode] = useState(false);

  const sections = useMemo(() => {
    const seen = new Set<string>();
    for (const chunk of chunks) {
      const path = chunk.section_path.join(" / ");
      if (path) seen.add(path);
    }
    return [...seen];
  }, [chunks]);

  async function run(
    scope: TranslateScope,
    label: string,
    body: Record<string, unknown>,
  ) {
    setLoading(scope);
    setError(null);
    setResult(null);
    try {
      const response = await translatePaper(paperId, { scope, ...body });
      setResult({ scope, label, response });
      setMarkdownMode(scope === "full");
    } catch (cause) {
      setError({ scope, error: cause });
    } finally {
      setLoading(null);
    }
  }

  function toggleSelection(id: string) {
    setSelectedIds((ids) =>
      ids.includes(id) ? ids.filter((item) => item !== id) : [...ids, id],
    );
  }

  return (
    <div className="sg-translate">
      <div className="sg-translate__entries">
        <div className="sg-entry">
          <h4 className="sg-qa__sub">摘要翻译</h4>
          <p className="sg-mono">{"{"}&quot;scope&quot;:&quot;abstract&quot;{"}"}</p>
          <button
            className="sg-btn"
            type="button"
            disabled={loading !== null}
            onClick={() => run("abstract", "摘要翻译", {})}
          >
            {loading === "abstract" ? "翻译中…" : "翻译摘要"}
          </button>
        </div>

        <div className="sg-entry">
          <h4 className="sg-qa__sub">章节翻译</h4>
          <select
            className="sg-input"
            value={section}
            onChange={(event) => setSection(event.target.value)}
          >
            <option value="">选择章节（section_path 前缀）</option>
            {sections.map((item) => (
              <option key={item} value={item}>
                {item}
              </option>
            ))}
          </select>
          <button
            className="sg-btn"
            type="button"
            disabled={loading !== null || !section}
            onClick={() =>
              run("section", `章节翻译 · ${section}`, {
                section_path: section.split(" / "),
              })
            }
          >
            {loading === "section" ? "翻译中…" : "翻译该章节"}
          </button>
        </div>

        <div className="sg-entry">
          <h4 className="sg-qa__sub">选区翻译</h4>
          <div className="sg-note">
            <span className="sg-tag sg-tag--warning">按整 Chunk 计</span>
            <p className="sg-note__text">
              后端当前只接受该论文已有的 chunk_id，按原文顺序翻译整段 Chunk；
              <strong>不支持 Chunk 内字符级选区</strong>，也不是逐词翻译。
              下方勾选的是完整的 Chunk。
            </p>
          </div>
          <div className="sg-picker__list sg-picker__list--compact">
            {chunks.slice(0, 40).map((chunk) => (
              <label className="sg-picker__item" key={chunk.chunk_id}>
                <input
                  type="checkbox"
                  checked={selectedIds.includes(chunk.chunk_id)}
                  onChange={() => toggleSelection(chunk.chunk_id)}
                />
                <span className="sg-mono">
                  p.{chunk.page_number} · {chunk.chunk_id.slice(-14)}
                </span>
                <span className="sg-prose">{chunk.text.slice(0, 60)}…</span>
              </label>
            ))}
          </div>
          <button
            className="sg-btn"
            type="button"
            disabled={loading !== null || selectedIds.length === 0}
            onClick={() =>
              run("selection", `选区翻译 · ${selectedIds.length} 个整 Chunk`, {
                chunk_ids: selectedIds,
              })
            }
          >
            {loading === "selection"
              ? "翻译中…"
              : `翻译选中 ${selectedIds.length} 个整 Chunk`}
          </button>
        </div>

        <div className="sg-entry">
          <h4 className="sg-qa__sub">全文翻译</h4>
          <p className="sg-mono">
            全篇 Markdown 版式视图；原文上限 600000 字符，超限须按章节/选区调用。
          </p>
          <button
            className="sg-btn"
            type="button"
            disabled={loading !== null}
            onClick={() => run("full", "全文翻译", {})}
          >
            {loading === "full" ? "翻译中（约需一分钟）…" : "翻译全文"}
          </button>
        </div>
      </div>

      {error ? (
        <div>
          <ErrorState
            title={`翻译请求失败（${error.scope}）· 未返回任何译文`}
            error={error.error}
          />
          <p className="sg-mono">
            缺配置时后端返回 502 / UPSTREAM_ERROR「环境变量未设置，未调用模型」；
            后端不提供无 Key 的摘录假译文，前端也不补。
          </p>
        </div>
      ) : null}

      {result ? (
        <>
          <div className="sg-stream__done">
            <span className="sg-tag sg-tag--muted">scope {result.response.scope}</span>
            <span className="sg-mono">target {result.response.target}</span>
            <span className="sg-mono">
              对齐段数 {result.response.segments.length}
            </span>
            <span className="sg-mono">
              服务商 {result.response.metadata.provider}
            </span>
            <span className="sg-mono">
              模型 {result.response.metadata.model}
            </span>
            <span className="sg-mono">
              耗时 {result.response.metadata.elapsed_seconds ?? "—"} s
            </span>
            <span className="sg-mono">
              {result.response.markdown
                ? `Markdown ${result.response.markdown.length} 字符`
                : "markdown null"}
            </span>
          </div>

          <p className="sg-mono">
            对齐口径：{result.response.metadata.alignment} · 版式来源：
            {result.response.metadata.layout_source}
          </p>
          {result.response.metadata.terminology.length > 0 ? (
            <p className="sg-mono">
              本次词表：{result.response.metadata.terminology.join("、")}
            </p>
          ) : null}

          {result.response.markdown ? (
            <label className="sg-checkbox">
              <input
                type="checkbox"
                checked={markdownMode}
                onChange={(event) => setMarkdownMode(event.target.checked)}
              />
              右栏用 Markdown 版式视图（否则逐段对照）
            </label>
          ) : null}

          <BilingualPane
            segments={result.response.segments}
            markdown={result.response.markdown}
            markdownMode={markdownMode}
          />
        </>
      ) : null}
    </div>
  );
}

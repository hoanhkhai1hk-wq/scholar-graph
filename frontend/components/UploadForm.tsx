"use client";

import { useState } from "react";
import Link from "next/link";
import { uploadBatch, uploadSingle } from "@/lib/api";
import type { BatchResult, PaperMeta } from "@/lib/types";
import ErrorState from "./ErrorState";

type Phase =
  | { kind: "idle" }
  | { kind: "running"; startedAt: number }
  | { kind: "done"; elapsedMs: number }
  | { kind: "error"; error: unknown; elapsedMs: number };

type ResultState =
  | { kind: "idle" }
  | { kind: "ok"; paper: PaperMeta }
  | { kind: "ok-batch"; result: BatchResult; fileCount: number }
  | { kind: "error"; error: unknown };

/**
 * 上传进度提示。
 * 后端是同步等待解析，没有进度事件，因此这里只展示真实可知的信息：
 * 已耗时、处理到第几个文件、当前提示文案。不伪造百分比进度。
 */
function useElapsed(phase: Phase) {
  const [now, setNow] = useState(() => Date.now());

  if (phase.kind === "running") {
    // 每 500ms 刷新一次计时，仅在提交期间生效
    if (typeof window !== "undefined") {
      setTimeout(() => setNow(Date.now()), 500);
    }
    return now - phase.startedAt;
  }
  if (phase.kind === "done" || phase.kind === "error") return phase.elapsedMs;
  return 0;
}

export default function UploadForm() {
  const [singleFile, setSingleFile] = useState<File | null>(null);
  const [batchFiles, setBatchFiles] = useState<File[]>([]);
  const [phase, setPhase] = useState<Phase>({ kind: "idle" });
  const [result, setResult] = useState<ResultState>({ kind: "idle" });
  const [doneCount, setDoneCount] = useState(0);

  const elapsed = useElapsed(phase);
  const running = phase.kind === "running";

  async function submitSingle() {
    if (!singleFile) return;
    const startedAt = Date.now();
    setPhase({ kind: "running", startedAt });
    setResult({ kind: "idle" });
    setDoneCount(0);
    try {
      const paper = await uploadSingle(singleFile);
      setDoneCount(1);
      setResult({ kind: "ok", paper });
      setPhase({ kind: "done", elapsedMs: Date.now() - startedAt });
    } catch (error) {
      setResult({ kind: "error", error });
      setPhase({ kind: "error", error, elapsedMs: Date.now() - startedAt });
    }
  }

  async function submitBatch() {
    if (batchFiles.length === 0) return;
    const startedAt = Date.now();
    setPhase({ kind: "running", startedAt });
    setResult({ kind: "idle" });
    setDoneCount(0);
    try {
      const batch = await uploadBatch(batchFiles);
      setDoneCount(batchFiles.length);
      setResult({
        kind: "ok-batch",
        result: batch,
        fileCount: batchFiles.length,
      });
      setPhase({ kind: "done", elapsedMs: Date.now() - startedAt });
    } catch (error) {
      setResult({ kind: "error", error });
      setPhase({ kind: "error", error, elapsedMs: Date.now() - startedAt });
    }
  }

  const totalFiles = batchFiles.length;

  return (
    <>
      <section className="sg-section">
        <div className="sg-section__head">
          <h2 className="sg-section__title">单篇上传</h2>
          <span className="sg-section__hint">POST /api/v1/papers</span>
        </div>

        <div className="sg-form">
          <input
            className="sg-input"
            type="file"
            accept="application/pdf,.pdf"
            onChange={(event) => {
              setSingleFile(event.target.files?.[0] ?? null);
              setResult({ kind: "idle" });
              setPhase({ kind: "idle" });
            }}
          />
          <button
            className="sg-btn"
            type="button"
            disabled={!singleFile || running}
            onClick={submitSingle}
          >
            {running ? "上传中…" : "上传"}
          </button>
        </div>

        {running ? (
          <div className="sg-progress-note">
            <span className="sg-tag sg-tag--info">
              已等待 {(elapsed / 1000).toFixed(1)} 秒
            </span>
            <p className="sg-mono">
              后端按文件顺序同步等待解析完成后才返回，中途没有进度事件；
              扫描件需要 OCR，实测约需 30–60 秒，请耐心等待，不要重复提交。
            </p>
          </div>
        ) : null}

        {result.kind === "ok" ? (
          <div>
            <p className="sg-result-line">
              <span className="sg-tag sg-tag--success">成功</span> paper_id{" "}
              <code className="sg-mono">{result.paper.id}</code>
              {phase.kind === "done" ? (
                <span className="sg-mono">
                  耗时 {(phase.elapsedMs / 1000).toFixed(1)} 秒
                </span>
              ) : null}
            </p>
            <Link href={`/papers/${result.paper.id}`}>查看该论文详情 →</Link>
          </div>
        ) : null}
        {result.kind === "error" ? (
          <ErrorState title="单篇上传失败" error={result.error} />
        ) : null}
      </section>

      <section className="sg-section">
        <div className="sg-section__head">
          <h2 className="sg-section__title">批量上传</h2>
          <span className="sg-section__hint">POST /api/v1/papers/batch</span>
        </div>

        <div className="sg-form">
          <input
            className="sg-input"
            type="file"
            accept="application/pdf,.pdf"
            multiple
            onChange={(event) => {
              setBatchFiles(Array.from(event.target.files ?? []));
              setResult({ kind: "idle" });
              setPhase({ kind: "idle" });
            }}
          />
          <button
            className="sg-btn"
            type="button"
            disabled={totalFiles === 0 || running}
            onClick={submitBatch}
          >
            {running ? "上传中…" : `上传 ${totalFiles} 个文件`}
          </button>
        </div>

        {running ? (
          <div className="sg-progress-note">
            <span className="sg-tag sg-tag--info">
              已等待 {(elapsed / 1000).toFixed(1)} 秒 · 共 {totalFiles} 个文件
            </span>
            <p className="sg-mono">
              批量按文件顺序同步处理，任一项失败也会继续处理后续文件；
              后端不返回逐文件进度事件，本提示只显示已等待时长与文件总数。
            </p>
          </div>
        ) : null}

        {result.kind === "ok-batch" ? (
          <div>
            <p className="sg-result-line">
              共提交 <strong>{result.fileCount}</strong> 个文件，成功{" "}
              <strong>{result.result.succeeded_count}</strong>、失败{" "}
              <strong>{result.result.failed_count}</strong>
              {phase.kind === "done" ? (
                <span className="sg-mono">
                  耗时 {(phase.elapsedMs / 1000).toFixed(1)} 秒
                </span>
              ) : null}
              {result.result.succeeded_count + result.result.failed_count ===
              result.fileCount ? (
                <span className="sg-tag sg-tag--success">
                  整批无丢项：成功数与失败数之和等于提交数
                </span>
              ) : (
                <span className="sg-tag sg-tag--error">
                  数量对不上：成功数与失败数之和不等于提交数
                </span>
              )}
            </p>

            <h3 className="sg-subhead">
              成功项（{result.result.succeeded_count}）
            </h3>
            {result.result.succeeded.length === 0 ? (
              <p className="sg-mono">无成功项</p>
            ) : (
              <table className="sg-table">
                <thead>
                  <tr>
                    <th className="sg-num">#</th>
                    <th>paper_id</th>
                    <th>初始状态</th>
                    <th className="sg-num">初始进度</th>
                  </tr>
                </thead>
                <tbody>
                  {result.result.succeeded.map((item, index) => (
                    <tr key={item.paper_id}>
                      <td className="sg-num">{index + 1}</td>
                      <td className="sg-mono">
                        <Link href={`/papers/${item.paper_id}`}>
                          {item.paper_id}
                        </Link>
                      </td>
                      <td>
                        <span className="sg-tag sg-tag--muted">
                          {item.parse_status.status}
                        </span>
                      </td>
                      <td className="sg-num">{item.parse_status.progress}%</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}

            <h3 className="sg-subhead">
              失败项（{result.result.failed_count}）
            </h3>
            {result.result.failed.length === 0 ? (
              <p className="sg-mono">无失败项</p>
            ) : (
              <table className="sg-table">
                <thead>
                  <tr>
                    <th className="sg-num">#</th>
                    <th>文件名</th>
                    <th>错误码</th>
                    <th>原因</th>
                  </tr>
                </thead>
                <tbody>
                  {result.result.failed.map((item, index) => (
                    <tr key={`${item.filename}-${index}`}>
                      <td className="sg-num">{index + 1}</td>
                      <td className="sg-mono">{item.filename}</td>
                      <td>
                        <span className="sg-tag sg-tag--error">
                          {item.error_code}
                        </span>
                      </td>
                      <td>{item.error_message}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        ) : null}
        {result.kind === "error" ? (
          <ErrorState title="批量上传失败" error={result.error} />
        ) : null}
      </section>
    </>
  );
}

"use client";

import { useState } from "react";
import Link from "next/link";
import { uploadBatch, uploadSingle } from "@/lib/api";
import type { BatchResult, PaperMeta } from "@/lib/types";
import ErrorState from "./ErrorState";

type SingleState =
  | { kind: "idle" }
  | { kind: "loading" }
  | { kind: "ok"; paper: PaperMeta }
  | { kind: "error"; error: unknown };

type BatchState =
  | { kind: "idle" }
  | { kind: "loading"; fileCount: number }
  | { kind: "ok"; result: BatchResult; fileCount: number }
  | { kind: "error"; error: unknown };

export default function UploadForm() {
  const [singleFile, setSingleFile] = useState<File | null>(null);
  const [batchFiles, setBatchFiles] = useState<File[]>([]);
  const [single, setSingle] = useState<SingleState>({ kind: "idle" });
  const [batch, setBatch] = useState<BatchState>({ kind: "idle" });

  async function submitSingle() {
    if (!singleFile) return;
    setSingle({ kind: "loading" });
    try {
      const paper = await uploadSingle(singleFile);
      setSingle({ kind: "ok", paper });
    } catch (error) {
      setSingle({ kind: "error", error });
    }
  }

  async function submitBatch() {
    if (batchFiles.length === 0) return;
    setBatch({ kind: "loading", fileCount: batchFiles.length });
    try {
      const result = await uploadBatch(batchFiles);
      setBatch({ kind: "ok", result, fileCount: batchFiles.length });
    } catch (error) {
      setBatch({ kind: "error", error });
    }
  }

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
              setSingle({ kind: "idle" });
            }}
          />
          <button
            className="sg-btn"
            type="button"
            disabled={!singleFile || single.kind === "loading"}
            onClick={submitSingle}
          >
            {single.kind === "loading" ? "上传中…" : "上传"}
          </button>
        </div>

        {single.kind === "ok" ? (
          <div>
            <p className="sg-result-line">
              <span className="sg-tag sg-tag--success">成功</span> paper_id{" "}
              <code className="sg-mono">{single.paper.id}</code>
            </p>
            <Link href={`/papers/${single.paper.id}`}>查看该论文详情 →</Link>
          </div>
        ) : null}
        {single.kind === "error" ? (
          <ErrorState title="单篇上传失败" error={single.error} />
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
              setBatch({ kind: "idle" });
            }}
          />
          <button
            className="sg-btn"
            type="button"
            disabled={batchFiles.length === 0 || batch.kind === "loading"}
            onClick={submitBatch}
          >
            {batch.kind === "loading" ? "上传中…" : `上传 ${batchFiles.length} 个文件`}
          </button>
        </div>

        {batch.kind === "ok" ? (
          <div>
            <p className="sg-result-line">
              共提交 <strong>{batch.fileCount}</strong> 个文件，成功{" "}
              <strong>{batch.result.succeeded_count}</strong>、失败{" "}
              <strong>{batch.result.failed_count}</strong>。
              {batch.result.succeeded_count + batch.result.failed_count ===
              batch.fileCount ? (
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
              成功项（{batch.result.succeeded_count}）
            </h3>
            {batch.result.succeeded.length === 0 ? (
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
                  {batch.result.succeeded.map((item, index) => (
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
              失败项（{batch.result.failed_count}）
            </h3>
            {batch.result.failed.length === 0 ? (
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
                  {batch.result.failed.map((item, index) => (
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
        {batch.kind === "error" ? (
          <ErrorState title="批量上传失败" error={batch.error} />
        ) : null}
      </section>
    </>
  );
}

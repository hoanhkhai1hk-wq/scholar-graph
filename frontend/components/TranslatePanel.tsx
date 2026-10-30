"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import type { Chunk, TranslateResponse, TranslateScope } from "@/lib/types";
import { getReading, workspacePost } from "@/lib/workspace";
import TaskMonitor, { type WorkspaceTask } from "./TaskMonitor";
import BilingualPane from "./BilingualPane";
import MarkdownView from "./MarkdownView";

export default function TranslatePanel({ paperId, chunks, pageCount = 1 }: { paperId: string; chunks: Chunk[]; pageCount?: number }) {
  const [scope, setScope] = useState<TranslateScope>("abstract");
  const [target, setTarget] = useState("zh");
  const [section, setSection] = useState("");
  const [page, setPage] = useState(1);
  const [pageChunks, setPageChunks] = useState(chunks.filter(c => c.page_number === 1));
  const [selected, setSelected] = useState<string[]>([]);
  const [taskId, setTaskId] = useState("");
  const [chineseTask, setChineseTask] = useState("");
  const [response, setResponse] = useState<TranslateResponse | null>(null);
  const [resultPage, setResultPage] = useState(1);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const key = `sg.translation.${paperId}`;
  useEffect(() => { setTaskId(localStorage.getItem(key) ?? ""); setChineseTask(localStorage.getItem(`${key}.zh`) ?? ""); }, [key]);
  const sections = useMemo(() => [...new Set(chunks.map(c => JSON.stringify(c.section_path)).filter(p => p !== "[]"))], [chunks]);
  useEffect(() => { let disposed = false; void getReading(paperId, page).then(value => { if (!disposed) setPageChunks(value.chunks); }).catch(cause => { if (!disposed) setError(cause.message); }); return () => { disposed = true; }; }, [paperId, page]);
  const result = useCallback((value: NonNullable<WorkspaceTask["result"]>) => {
    const translation = value.translation as TranslateResponse | undefined;
    if (translation) { setResponse(translation); setResultPage(translation.segments[0]?.page_number ?? 1); }
  }, []);
  function remember(id: string) { setTaskId(id); localStorage.setItem(key, id); }
  function exportTranslation() { if (!response || incomplete || outdatedCode) return; const text = response.markdown ?? response.segments.map(s => s.translated_text).join("\n\n"); const url = URL.createObjectURL(new Blob([text], { type: "text/markdown;charset=utf-8" })); const a = document.createElement("a"); a.href = url; a.download = "论文译文.md"; a.click(); setTimeout(() => URL.revokeObjectURL(url), 1000); }
  async function run() {
    setBusy(true); setError(""); setResponse(null);
    try {
      const chineseSource = target === "en" ? (localStorage.getItem(`${key}.zh.${scope}`)
        || (scope === "abstract" ? localStorage.getItem(`${key}.zh.full`) : null) || chineseTask) : null;
      const task = await workspacePost<WorkspaceTask>(`/papers/${paperId}/translation-tasks`, {
        scope, target, ...(scope === "section" ? { section_path: JSON.parse(section) } : {}),
        ...(scope === "selection" ? { chunk_ids: selected } : {}), ...(chineseSource ? { chinese_task_id: chineseSource } : {}),
      });
      remember(task.id);
      if (target === "zh") { setChineseTask(task.id); localStorage.setItem(`${key}.zh`, task.id); localStorage.setItem(`${key}.zh.${scope}`, task.id); }
    } catch (cause) { setError(cause instanceof Error ? cause.message : "翻译任务未能开始。"); }
    finally { setBusy(false); }
  }
  const pages = [...new Set(response?.segments.map(segment => segment.page_number) ?? [])];
  const incomplete = Boolean(response && (response.metadata.complete === false || response.segments.length === 0 || typeof response.metadata.expected_segments === "number" && response.segments.length !== response.metadata.expected_segments));
  const outdatedCode = Boolean(response && response.metadata.code_layout_version !== "pdf-fenced-code-v1"
    && response.segments.some(segment => /```|~~~/.test(segment.source_text)));
  return <div className="sg-translate">
    <h2 className="sg-section__title">双语阅读与翻译</h2><p className="sg-lede">译文逐段对应原文，保留公式和代码。任务可停止、刷新查看和重试；文字选区及悬停翻译在“原版式”中使用。</p>
    <div className="sg-form"><label className="sg-field">翻译方向<select className="sg-input" value={target} onChange={event => { setTarget(event.target.value); if (event.target.value === "en" && !["abstract", "full"].includes(scope)) setScope("abstract"); }}><option value="zh">英译中</option><option value="en">中译英</option></select></label>
      <label className="sg-field">翻译范围<select className="sg-input" value={scope} onChange={event => setScope(event.target.value as TranslateScope)}><option value="abstract">摘要</option>{target === "zh" ? <><option value="section">指定章节</option><option value="selection">勾选段落</option></> : null}<option value="full">全文</option></select></label>
      {scope === "section" ? <label className="sg-field">章节<select className="sg-input" value={section} onChange={event => setSection(event.target.value)}><option value="">请选择章节</option>{sections.map(path => <option key={path} value={path}>{JSON.parse(path).join(" / ")}</option>)}</select></label> : null}
      {target === "en" ? <p>直接翻译中文论文；英文论文可先完成对应范围的英译中任务，再从已保存的中文译文回译。</p> : null}
    </div>
    {scope === "selection" ? <><label className="sg-field">查看原文页<input className="sg-input sg-input--narrow" type="number" min={1} max={pageCount} value={page} onChange={event => { const n = Number(event.target.value); if (n >= 1 && n <= pageCount) setPage(n); }} /></label><p>已选择 {selected.length} 段，可跨页勾选。</p><div className="sg-picker__list">{pageChunks.map(chunk => <label className="sg-picker__item" key={chunk.chunk_id}><input type="checkbox" checked={selected.includes(chunk.chunk_id)} onChange={() => setSelected(ids => ids.includes(chunk.chunk_id) ? ids.filter(id => id !== chunk.chunk_id) : [...ids, chunk.chunk_id])} /><span>第 {chunk.page_number} 页 · {chunk.text.slice(0, 180)}</span></label>)}</div></> : null}
    <button className="sg-btn" disabled={busy || scope === "section" && !section || scope === "selection" && !selected.length} title={scope === "section" && !section ? "请先选择章节" : scope === "selection" && !selected.length ? "请先勾选段落" : undefined} onClick={() => void run()}>{busy ? "正在创建任务…" : "开始翻译"}</button>
    {error ? <p role="alert" className="sg-error">{error}</p> : null}
    {taskId ? <TaskMonitor taskId={taskId} onTaskChange={remember} onResult={result} /> : null}
    {response ? <><h3>{incomplete ? "译文尚未完成" : outdatedCode ? "历史译文待重新校验" : "已校验译文"} · 已校验 {response.segments.length} 段</h3>{incomplete ? <p role="alert" className="sg-error">部分原文段落尚未通过校验，当前内容不是完整译文。已校验部分保留，请查看失败原因并重试任务；完成前不能导出。</p> : null}{outdatedCode ? <p role="alert" className="sg-error">这份历史译文尚未校验代码顺序与缩进，请选择原来的翻译方向和范围，点击“开始翻译”重新生成后导出。</p> : null}<p>两栏均可滚动，点击段落可对齐另一栏。</p><label className="sg-field">译文页<select className="sg-input" value={resultPage} onChange={event => setResultPage(Number(event.target.value))}>{pages.map(p => <option key={p} value={p}>第 {p} 页</option>)}</select></label><BilingualPane segments={response.segments.filter(s => s.page_number === resultPage)} markdown={null} markdownMode={false} target={response.target} /><button className="sg-btn sg-btn--ghost" disabled={outdatedCode || incomplete} title={incomplete ? "全部段落通过校验后才可导出" : outdatedCode ? "重新生成并校验后即可导出" : undefined} onClick={exportTranslation}>导出译文</button>{response.markdown ? <details><summary>查看全文排版译文</summary><MarkdownView markdown={response.markdown} /></details> : null}</> : null}
  </div>;
}
